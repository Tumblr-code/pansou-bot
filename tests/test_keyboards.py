from keyboards import AD_LINKS, create_ad_button_rows


def test_ad_links_use_examplestore_destinations() -> None:
    assert AD_LINKS == (
        ("🤖 店铺助手", "https://t.me/ExampleStoreRobot"),
        ("📢 频道", "https://t.me/ExampleStoreChannel"),
        ("💬 群组", "https://t.me/ExampleStoreGroup"),
    )

    rows = create_ad_button_rows()
    assert [(button.text, button.url) for row in rows for button in row] == list(AD_LINKS)
