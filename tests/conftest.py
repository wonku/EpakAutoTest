import pytest

from config import settings


@pytest.fixture(scope="function")
def mall_ui_page(playwright_instance):
    launch_kwargs = {
        "headless": settings.ESB_UI_HEADLESS,
        "slow_mo": settings.SLOW_MO,
    }
    if settings.BROWSER_EXECUTABLE_PATH:
        launch_kwargs["executable_path"] = settings.BROWSER_EXECUTABLE_PATH
    browser = playwright_instance.chromium.launch(**launch_kwargs)
    context = browser.new_context(
        viewport={
            "width": settings.ESB_UI_VIEWPORT_WIDTH,
            "height": settings.ESB_UI_VIEWPORT_HEIGHT,
        }
    )
    page = context.new_page()
    yield page
    for open_page in list(context.pages):
        try:
            open_page.close()
        except Exception:
            pass
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
