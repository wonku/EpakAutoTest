import allure
import pytest

from tests.test_mall_ui_inspection import ESBAO_SITE, run_mall_inspection


@pytest.mark.esbao
@allure.feature(ESBAO_SITE.feature)
@allure.story(ESBAO_SITE.story)
@allure.title(ESBAO_SITE.title)
def test_esbao_mall_home_and_product_flow(mall_ui_page, request):
    run_mall_inspection(mall_ui_page, ESBAO_SITE, request)
