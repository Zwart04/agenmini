import pytest_asyncio
@pytest_asyncio.fixture(autouse=True)
async def close_http_session():
    yield
    from app import llm
    if llm._session is not None and not llm._session.closed:
        await llm._session.close()
    llm._session=None
