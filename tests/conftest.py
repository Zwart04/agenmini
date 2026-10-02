import pytest_asyncio
@pytest_asyncio.fixture(autouse=True)
async def close_http_session():
    from app import llm
    original_chat=llm.chat
    yield
    llm.chat=original_chat
    from app import llm
    if llm._session is not None and not llm._session.closed:
        await llm._session.close()
    llm._session=None
