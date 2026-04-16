"""Test interaction correlation between instances."""

import asyncio
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from unigate.adapters import InternalAdapter
from unigate.kernel import Exchange
from unigate.message import Message, Sender, Interactive, InteractionType
from unigate.stores import InMemoryStores


@pytest.fixture
def exchange():
    """Create exchange with two instances (sync fixture)."""
    stores = InMemoryStores()
    exc = Exchange(
        inbox=stores,
        outbox=stores,
        sessions=stores,
        dedup=stores,
        interactions=stores,
    )
    
    sms = InternalAdapter('sms', None, exc)
    web = InternalAdapter('web', None, exc)
    exc.register_instance('sms', sms)
    exc.register_instance('web', web)
    
    return exc, sms, web


@pytest.mark.asyncio
async def test_interactive_response_correlates_across_instances(exchange):
    """SMS starts, handler sends interactive, Web user responds - correlation works."""
    exc, sms, web = exchange
    responses = []
    
    @exc.set_handler
    async def handle(msg):
        if msg.interactive and msg.interactive.response:
            responses.append(msg.interactive.response.value)
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance='handler',
                sender=Sender(platform_id='bot', name='Bot'),
                ts=datetime.now(timezone.utc),
                text=f"You said: {msg.interactive.response.value}"
            )
        
        if msg.text == 'start':
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance='handler',
                sender=Sender(platform_id='bot', name='Bot'),
                ts=datetime.now(timezone.utc),
                interactive=Interactive(
                    interaction_id=str(uuid4()),
                    type=InteractionType.CONFIRM,
                    prompt='Continue?',
                    options=['yes', 'no'],
                    timeout_seconds=60,
                    context={'action': 'test'}
                )
            )
        return None
    
    session_id = str(uuid4())
    
    # Step 1: SMS user starts
    await exc.ingest('sms', {
        'id': str(uuid4()),
        'session_id': session_id,
        'sender_id': 'user_sms',
        'sender_name': 'SMS User',
        'text': 'start',
        'ts': datetime.now(timezone.utc).isoformat()
    })
    
    # Step 2: Get pending interaction
    pending = await exc._interactions.get_interaction_by_session(session_id)
    assert pending is not None
    int_id = pending.interaction_id
    
    # Step 3: Web user responds
    await exc.ingest('web', {
        'id': str(uuid4()),
        'session_id': session_id,
        'sender_id': 'user_web',
        'sender_name': 'Web User',
        'text': 'yes',
        'ts': datetime.now(timezone.utc).isoformat(),
        'interactive_response': {
            'interaction_id': int_id,
            'value': 'yes'
        }
    })
    
    # Verify correlation happened
    assert len(responses) == 1
    assert responses[0] == 'yes'
    
    # Verify interaction.correlated event
    events = [e for e in exc.events if 'interaction' in e.name]
    event_names = [e.name for e in events]
    assert 'interaction.pending' in event_names
    assert 'interaction.correlated' in event_names


@pytest.mark.asyncio
async def test_interactive_response_same_instance(exchange):
    """SMS user starts and responds on same instance."""
    exc, sms, web = exchange
    responses = []
    
    @exc.set_handler
    async def handle(msg):
        if msg.interactive and msg.interactive.response:
            responses.append(msg.interactive.response.value)
            return None
        
        if msg.text == 'start':
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance='handler',
                sender=Sender(platform_id='bot', name='Bot'),
                ts=datetime.now(timezone.utc),
                interactive=Interactive(
                    interaction_id=str(uuid4()),
                    type=InteractionType.CONFIRM,
                    prompt='Confirm?',
                    options=['yes', 'no'],
                )
            )
        return None
    
    session_id = str(uuid4())
    
    # SMS starts
    await exc.ingest('sms', {
        'id': str(uuid4()),
        'session_id': session_id,
        'sender_id': 'user_sms',
        'sender_name': 'SMS User',
        'text': 'start',
        'ts': datetime.now(timezone.utc).isoformat()
    })
    
    # SMS responds (same instance)
    pending = await exc._interactions.get_interaction(session_id, 'sms')
    await exc.ingest('sms', {
        'id': str(uuid4()),
        'session_id': session_id,
        'sender_id': 'user_sms',
        'sender_name': 'SMS User',
        'text': 'yes',
        'ts': datetime.now(timezone.utc).isoformat(),
        'interactive_response': {
            'interaction_id': pending.interaction_id,
            'value': 'yes'
        }
    })
    
    assert len(responses) == 1
    assert responses[0] == 'yes'


@pytest.mark.asyncio
async def test_interactive_timeout(exchange):
    """Interactive that times out is cleaned up."""
    exc, sms, web = exchange
    
    @exc.set_handler
    async def handle(msg):
        if msg.text == 'start':
            return Message(
                id=str(uuid4()),
                session_id=msg.session_id,
                from_instance='handler',
                sender=Sender(platform_id='bot', name='Bot'),
                ts=datetime.now(timezone.utc),
                interactive=Interactive(
                    interaction_id=str(uuid4()),
                    type=InteractionType.CONFIRM,
                    prompt='Continue?',
                    options=['yes', 'no'],
                    timeout_seconds=1,  # 1 second timeout
                )
            )
        return None
    
    session_id = str(uuid4())
    
    await exc.ingest('sms', {
        'id': str(uuid4()),
        'session_id': session_id,
        'sender_id': 'user_sms',
        'sender_name': 'SMS User',
        'text': 'start',
        'ts': datetime.now(timezone.utc).isoformat()
    })
    
    # Verify pending interaction exists
    pending = await exc._interactions.get_interaction_by_session(session_id)
    assert pending is not None
    
    # Wait for timeout
    await asyncio.sleep(1.5)
    
    # Cleanup expired
    expired = await exc._interactions.cleanup_expired(datetime.now(timezone.utc))
    assert len(expired) == 1
    assert expired[0].interaction_id == pending.interaction_id
    
    # Verify pending is removed
    pending = await exc._interactions.get_interaction_by_session(session_id)
    assert pending is None
