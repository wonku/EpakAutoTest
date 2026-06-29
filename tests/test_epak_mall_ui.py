import allure
import pytest

from tests.test_mall_ui_inspection import EPAK_SITE, run_mall_inspection


@pytest.mark.epak
@allure.feature(EPAK_SITE.feature)
@allure.story(EPAK_SITE.story)
@allure.title(EPAK_SITE.title)
def test_epak_mall_home_and_product_flow(mall_ui_page, request):
    run_mall_inspection(mall_ui_page, EPAK_SITE, request)
