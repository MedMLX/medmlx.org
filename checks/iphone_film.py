# /// script
# requires-python = ">=3.13"
# dependencies = ["pymobiledevice3==11.63.0", "pillow==13.0.0"]
# ///
"""Tap the film controls in a physical iPhone's isolated Safari automation tab."""

import asyncio
import os
from collections.abc import Callable
from io import BytesIO
from typing import TypedDict, cast

from PIL import Image, ImageChops, ImageStat
from pymobiledevice3.lockdown import DeviceClass, create_using_usbmux
from pymobiledevice3.services.web_protocol.driver import WebDriver
from pymobiledevice3.services.webinspector import SAFARI, WebinspectorService


class Film(TypedDict):
    time: float
    duration: float
    paused: bool
    seeking: bool
    ready: bool


async def state(driver: WebDriver) -> Film:
    """Read the media state from the current Safari document."""
    return cast(Film, await driver.execute_script("""
        const v = document.querySelector('.hero-video');
        return {time: v.currentTime, duration: v.duration, paused: v.paused, seeking: v.seeking,
                ready: !document.querySelector('.film-controls').hidden
                    && !document.querySelector('[data-film-next]').disabled};
    """))


async def wait(driver: WebDriver, predicate: Callable[[Film], bool], label: str) -> Film:
    try:
        async with asyncio.timeout(15):
            while True:
                film = await state(driver)
                if predicate(film):
                    return film
                await asyncio.sleep(0.1)
    except TimeoutError as error:
        raise AssertionError(f"{label}: {await state(driver)}") from error


async def tap(driver: WebDriver, control: str) -> None:
    """Send a touch down and up at the control's viewport coordinates."""
    point = cast(dict[str, int], await driver.execute_script("""
        const button = document.querySelector('[data-film-' + arguments[0] + ']');
        button.scrollIntoView({block: 'nearest', behavior: 'instant'});
        const box = button.getBoundingClientRect();
        return {x: Math.round(box.left + box.width / 2), y: Math.round(box.top + box.height / 2)};
    """, control))
    finger = {"sourceId": "finger", "location": point}
    await driver.session.perform_interaction_sequence(
        [{"sourceId": "finger", "sourceType": "Touch"}],
        [{"states": [{**finger, "pressedButton": "Left"}]}, {"states": [finger]}],
    )


def difference(first: Image.Image, second: Image.Image) -> float:
    """Mean absolute RGB difference over the film's visible crop."""
    assert first.size == second.size, f"Film crop changed size from {first.size} to {second.size}"
    return sum(ImageStat.Stat(ImageChops.difference(first, second)).mean) / 3


async def check(driver: WebDriver) -> None:
    film = await wait(driver, lambda f: f["ready"], "Controls unavailable")
    if film["paused"]:
        await tap(driver, "toggle")
    await wait(driver, lambda f: not f["paused"] and f["time"] > film["time"] + 0.2, "Play")
    await tap(driver, "toggle")
    paused = await wait(driver, lambda f: f["paused"], "Pause")
    await asyncio.sleep(0.35)
    held = await state(driver)
    assert held["paused"] and abs(held["time"] - paused["time"]) < 1 / 24, "Playback advanced while paused"

    duration = paused["duration"] / 6
    scene = int(paused["time"] / duration)
    picture = await driver.find_element_by_css_selector(".hero-media")
    assert picture is not None
    aspect = float(await driver.execute_script("""
        const box = document.querySelector('.hero-media').getBoundingClientRect();
        return box.width / box.height;
    """))
    scale = await driver.execute_script("return visualViewport.scale")
    frames: dict[int, Image.Image] = {}
    previous: Image.Image | None = None
    for direction in [1] * 7 + [-1] * 6:
        scene = (scene + direction) % 6
        await tap(driver, "next" if direction == 1 else "back")
        await wait(driver, lambda f, target=scene: f["paused"] and not f["seeking"] and int(f["time"] / duration) == target,
                   f"Seek to scene {scene + 1}")
        try:
            async with asyncio.timeout(5):
                while True:
                    frame = Image.open(BytesIO(await picture.get_screenshot_as_png())).convert("RGB")
                    # Safari includes the overflowing left portion of the video in
                    # element screenshots. The visible film is aligned to the right.
                    width = round(frame.height * aspect)
                    frame = frame.crop((frame.width - width, 0, frame.width, frame.height))
                    changed = previous is None or difference(previous, frame) > 1
                    if changed and (scene not in frames or difference(frames[scene], frame) < 1):
                        break
                    await asyncio.sleep(0.1)
        except TimeoutError as error:
            raise AssertionError(f"Incorrect picture for scene {scene + 1}") from error
        assert await driver.execute_script("return visualViewport.scale") == scale, "Control tap zoomed the page"
        frames.setdefault(scene, frame)
        previous = frame

    stopped = await state(driver)
    await tap(driver, "toggle")
    await wait(driver, lambda f: not f["paused"] and f["time"] > stopped["time"] + 0.2, "Resume")


async def main() -> None:
    url = os.environ.get("FILM_URL", "https://medmlx.org/")
    async with await create_using_usbmux(connection_type="USB") as phone:
        assert phone.device_class == DeviceClass.IPHONE, "Connect a physical iPhone by USB"
        async with WebinspectorService(phone) as inspector:
            safari = await inspector.open_app(SAFARI, 15)
            session = await inspector.automation_session(safari)
            driver = WebDriver(session)
            try:
                await driver.start_session()
                await driver.get(url)
                print(f"Physical {phone.product_type}, iOS {phone.product_version}, Safari at {url}", flush=True)
                await check(driver)
                print("Passed touch playback, pause, all six pictures, wraparound, previous and resume.")
            finally:
                await session.stop_session()


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), 120))
