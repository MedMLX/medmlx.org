# /// script
# requires-python = ">=3.13"
# dependencies = ["pymobiledevice3==11.63.0", "pillow==13.0.0"]
# ///
"""Exercise the mobile menu and the model catalog's playable output views in Safari."""

import asyncio
from io import BytesIO
from typing import cast

from iphone_film import difference, run_safari, touch
from PIL import Image
from pymobiledevice3.services.web_protocol.driver import WebDriver
from pymobiledevice3.services.web_protocol.element import WebElement


async def expect(driver: WebDriver, expression: str, label: str) -> None:
    try:
        async with asyncio.timeout(15):
            while not await driver.execute_script(f"return Boolean({expression})"):
                await asyncio.sleep(0.1)
    except TimeoutError as error:
        raise AssertionError(f"{await driver.get_current_url()}: {label}") from error


async def picture(video: WebElement) -> Image.Image:
    return Image.open(BytesIO(await video.get_screenshot_as_png())).convert("RGB")


async def check_view(driver: WebDriver, mode: str) -> None:
    selector = f'[data-scrub="{mode}"]'
    video = f"document.querySelector('{selector} video')"
    await driver.execute_script("document.querySelector(arguments[0]).scrollIntoView({block:'center'})", selector)
    await expect(driver, f"{video}.currentTime > 0 && !{video}.paused", f"{mode} playback")
    scale = float(await driver.execute_script("return visualViewport.scale"))
    toggle = "main [data-media-toggle]"
    await touch(driver, toggle, block="center")
    await expect(driver, f"{video}.paused", "pause animation")
    await touch(driver, toggle, block="center")
    await expect(driver, f"!{video}.paused", "resume animation")
    await touch(driver, selector, block="center")
    await expect(driver, f"{video}.paused && document.querySelector('[data-media-toggle]').ariaLabel.startsWith('Play ')",
                 "hold animation and offer Play")
    element = await driver.find_element_by_css_selector(selector + " video")
    assert element is not None
    before = await picture(element)
    start, end = ((0.5, 0.35), (0.5, 0.67)) if mode == "slices" else ((0.35, 0.5), (0.67, 0.5))
    for a, b in ((start, end), (end, start)):
        previous_time = float(await driver.execute_script(f"return {video}.currentTime"))
        await touch(driver, selector, a, b, block="center")
        await expect(driver, f"{video}.paused && !{video}.seeking && Math.abs({video}.currentTime - {previous_time}) > 0.035",
                     f"{mode} drag")
        try:
            async with asyncio.timeout(5):
                while difference(before, after := await picture(element)) <= 0.65:
                    await asyncio.sleep(0.1)
        except TimeoutError as error:
            raise AssertionError(f"{await driver.get_current_url()}: frozen {mode} image after dragging") from error
        assert await driver.execute_script("return visualViewport.scale") == scale, "Model controls zoomed the page"
        before = after

    # Restart the held view directly and with the visible Play button.
    for control in (selector, toggle):
        held = float(await driver.execute_script(f"return {video}.currentTime"))
        await touch(driver, control, block="center")
        await expect(driver, f"!{video}.paused && Math.abs({video}.currentTime - {held}) > 0.1",
                     "resume after inspecting a frame")
        await touch(driver, selector, block="center")
        await expect(driver, f"{video}.paused", "pause again")


async def check_models(driver: WebDriver) -> None:
    await touch(driver, ".menu-toggle")
    await expect(driver, "document.querySelector('.menu-toggle').ariaExpanded === 'true'", "open navigation")
    await touch(driver, '#site-nav a[href="/models/"]')
    await expect(driver, "location.pathname === '/models/' && document.querySelector('.menu-toggle').ariaExpanded === 'false'",
                 "open Models and close navigation")
    urls = cast(list[str], await driver.execute_script("""
        return [...new Set(Array.from(document.querySelectorAll('.catalog-item h3 a[data-route]'), a => a.href))];
    """))
    assert urls, "No model pages linked from the catalog"
    tested: set[str] = set()
    for url in urls:
        await driver.get(url)
        modes = cast(list[str], await driver.execute_script("return Array.from(document.querySelectorAll('[data-scrub]'), el => el.dataset.scrub)"))
        for i, mode in enumerate(modes):
            if i:
                await touch(driver, f'[data-view="{mode}"]', block="center")
            await check_view(driver, mode)
            tested.add(mode)
            print(f"Passed {url} {mode}", flush=True)
        if len(modes) > 1:
            await touch(driver, '[data-view="turn"]', block="center")
            await expect(driver, "document.querySelector('[data-scrub=turn]').hidden === false", "return to 3D")
    assert tested == {"turn", "slices", "loop"}, f"Tested view types: {tested}"


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(run_safari(check_models), 300))
