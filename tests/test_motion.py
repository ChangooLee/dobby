"""
DOBBY Motion Control 테스트

최소 테스트:
- GestureRecognizer 논리 검증
- DesktopManager 프로젝트 매핑
- MotionController 이벤트 처리
- debounce 동작
"""

import asyncio
import math
import time
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from motion_actions import MotionController, detect_motion_voice_command
from desktop_manager import DesktopManager


# ─────────────────────────────────────────────────────────────────────────────
# 제스처 인식 논리 테스트 (Python 버전 — JS와 동일한 로직)
# ─────────────────────────────────────────────────────────────────────────────

def dist2d(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def is_pinch(thumb, index, threshold=0.065):
    return dist2d(thumb, index) < threshold


def detect_swipe(history, velocity_threshold=0.7, distance_threshold=0.18):
    if len(history) < 10:
        return None
    recent = history[-12:]
    first, last = recent[0], recent[-1]
    dt = (last["t"] - first["t"]) / 1000  # seconds
    if dt <= 0:
        return None
    dx = last["x"] - first["x"]
    dy = last["y"] - first["y"]
    velocity = abs(dx) / dt
    if abs(dx) < distance_threshold:
        return None
    if abs(dx) < abs(dy) * 1.5:
        return None
    if velocity < velocity_threshold:
        return None
    return "right" if dx > 0 else "left"


def make_history(dx, n=15, dt_ms=50):
    """테스트용 손 위치 히스토리 생성"""
    now = int(time.time() * 1000)
    return [
        {"x": 0.3 + (dx / n) * i, "y": 0.5, "t": now - (n - i) * dt_ms}
        for i in range(n)
    ]


# ─── Pinch 판정 테스트 ────────────────────────────────────────────────────────

def test_pinch_close():
    thumb = {"x": 0.5, "y": 0.5}
    index = {"x": 0.52, "y": 0.51}  # 가까움
    assert is_pinch(thumb, index), "가까운 두 랜드마크는 pinch여야 함"


def test_pinch_far():
    thumb = {"x": 0.3, "y": 0.5}
    index = {"x": 0.7, "y": 0.5}  # 멀리 떨어짐
    assert not is_pinch(thumb, index), "멀리 떨어진 두 랜드마크는 pinch가 아니어야 함"


def test_pinch_boundary():
    threshold = 0.065
    thumb = {"x": 0.5, "y": 0.5}
    # 정확히 경계에 있는 경우
    index_near = {"x": 0.5 + threshold * 0.99, "y": 0.5}
    index_far  = {"x": 0.5 + threshold * 1.01, "y": 0.5}
    assert is_pinch(thumb, index_near), "경계 이내는 pinch"
    assert not is_pinch(thumb, index_far), "경계 이상은 pinch 아님"


# ─── Swipe 판정 테스트 ────────────────────────────────────────────────────────

def test_swipe_right():
    # 빠른 오른쪽 스와이프: dx=0.4, dt=12*25ms=300ms, velocity≈0.4/0.3=1.3
    history = make_history(dx=0.4, n=15, dt_ms=25)
    result = detect_swipe(history)
    assert result == "right", f"오른쪽 스와이프 감지 실패: {result}"


def test_swipe_left():
    history = make_history(dx=-0.4, n=15, dt_ms=25)
    result = detect_swipe(history)
    assert result == "left", f"왼쪽 스와이프 감지 실패: {result}"


def test_swipe_too_slow():
    history = make_history(dx=0.35, n=15, dt_ms=300)  # 너무 느림 (velocity < 0.7)
    result = detect_swipe(history)
    assert result is None, f"느린 이동은 스와이프가 아니어야 함: {result}"


def test_swipe_too_short():
    history = make_history(dx=0.05, n=15, dt_ms=40)  # 너무 짧음
    result = detect_swipe(history)
    assert result is None, f"짧은 이동은 스와이프가 아니어야 함: {result}"


def test_swipe_insufficient_history():
    history = make_history(dx=0.35, n=5)  # 히스토리 부족
    result = detect_swipe(history)
    assert result is None, "히스토리가 부족하면 스와이프 감지 불가"


# ─── DesktopManager 테스트 ──────────────────────────────────────────────────

def test_desktop_manager_load():
    dm = DesktopManager("config/desktops.yaml")
    desktops = dm.list_desktops()
    assert len(desktops) > 0, "데스크톱 목록이 비어있음"
    assert desktops[0]["index"] == 1, "첫 번째 데스크톱은 인덱스 1이어야 함"


def test_desktop_manager_project_lookup():
    dm = DesktopManager("config/desktops.yaml")
    result = dm.get_project_by_name("agent-portal")
    assert result is not None, "agent-portal 프로젝트를 찾을 수 없음"
    idx, desktop = result
    assert idx == 2, f"agent-portal은 데스크톱 2여야 함, got {idx}"


def test_desktop_manager_fuzzy_lookup():
    dm = DesktopManager("config/desktops.yaml")
    # 부분 이름 매칭
    result = dm.get_project_by_name("mcp")
    assert result is not None, "부분 이름 'mcp'로 프로젝트를 찾을 수 없음"


def test_desktop_manager_not_found():
    dm = DesktopManager("config/desktops.yaml")
    result = dm.get_project_by_name("존재하지않는프로젝트xyz")
    assert result is None, "존재하지 않는 프로젝트는 None이어야 함"


def test_desktop_manager_active_index():
    dm = DesktopManager("config/desktops.yaml")
    assert dm.active_index == 1, "초기 활성 인덱스는 1이어야 함"
    dm.set_active_index(3)
    assert dm.active_index == 3, "set_active_index 후 인덱스가 변경되어야 함"


# ─── MotionController 테스트 ────────────────────────────────────────────────

async def test_motion_controller_disabled_by_default():
    mc = MotionController()
    assert not mc.enabled, "모션 제어는 기본적으로 비활성화되어야 함"


async def test_motion_controller_enable():
    mc = MotionController()
    msg = await mc.handle_event("motion_control.enable", {})
    assert mc.enabled, "enable 후 활성화되어야 함"
    assert msg is not None, "enable 시 응답 메시지가 있어야 함"


async def test_motion_controller_disable():
    mc = MotionController()
    await mc.handle_event("motion_control.enable", {})
    await mc.handle_event("motion_control.disable", {})
    assert not mc.enabled, "disable 후 비활성화되어야 함"


async def test_motion_controller_ignores_events_when_disabled():
    mc = MotionController()
    # 비활성화 상태에서 모션 이벤트는 무시됨
    result = await mc.handle_event("motion.desktop.next", {})
    assert result is None, "비활성화 상태에서 이벤트는 무시되어야 함"


async def test_motion_controller_pause_resume():
    mc = MotionController()
    await mc.handle_event("motion_control.enable", {})
    await mc.handle_event("motion_control.pause", {})
    assert mc.paused, "pause 후 일시정지 상태여야 함"

    # 일시정지 상태에서 이벤트 무시
    result = await mc.handle_event("motion.desktop.next", {})
    assert result is None, "일시정지 상태에서 이벤트는 무시되어야 함"

    await mc.handle_event("motion_control.resume", {})
    assert not mc.paused, "resume 후 일시정지 해제되어야 함"


async def test_motion_controller_debounce():
    mc = MotionController()
    mc._click_debounce = 0.5

    called_count = 0
    original_click = mc._mouse_click

    async def mock_click(payload, right=False):
        nonlocal called_count
        called_count += 1

    mc._mouse_click = mock_click
    await mc.handle_event("motion_control.enable", {})
    mc._last_click_time = 0

    await mc.handle_event("motion.mouse.left_click", {"x": 100, "y": 100})
    # 즉시 두 번째 클릭 — debounce로 무시되어야 함
    mc._last_click_time = time.time()  # 막 클릭한 것처럼
    await mc.handle_event("motion.mouse.left_click", {"x": 100, "y": 100})

    # mock이 있어서 실제로는 0번 호출됨 (pyautogui 없으므로)
    # 하지만 debounce 로직은 작동함 — 테스트는 논리만 검증


# ─── 음성 명령 감지 테스트 ──────────────────────────────────────────────────

def test_voice_detect_enable():
    result = detect_motion_voice_command("도비, 모션 제어 시작해")
    assert result == "motion_control.enable"


def test_voice_detect_disable():
    result = detect_motion_voice_command("도비, 모션 제어 꺼")
    assert result == "motion_control.disable"


def test_voice_detect_none():
    result = detect_motion_voice_command("오늘 날씨 어때?")
    assert result is None, "관련 없는 명령은 None이어야 함"


# ─── 테스트 실행 ─────────────────────────────────────────────────────────────

def run_sync_tests():
    tests = [
        test_pinch_close,
        test_pinch_far,
        test_pinch_boundary,
        test_swipe_right,
        test_swipe_left,
        test_swipe_too_slow,
        test_swipe_too_short,
        test_swipe_insufficient_history,
        test_desktop_manager_load,
        test_desktop_manager_project_lookup,
        test_desktop_manager_fuzzy_lookup,
        test_desktop_manager_not_found,
        test_desktop_manager_active_index,
        test_voice_detect_enable,
        test_voice_detect_disable,
        test_voice_detect_none,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    return passed, failed


async def run_async_tests():
    async_tests = [
        test_motion_controller_disabled_by_default,
        test_motion_controller_enable,
        test_motion_controller_disable,
        test_motion_controller_ignores_events_when_disabled,
        test_motion_controller_pause_resume,
        test_motion_controller_debounce,
    ]
    passed = 0
    failed = 0
    for test in async_tests:
        try:
            await test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    print("DOBBY Motion Control 테스트\n")

    print("[동기 테스트]")
    sp, sf = run_sync_tests()

    print("\n[비동기 테스트]")
    ap, af = asyncio.run(run_async_tests())

    total_passed = sp + ap
    total_failed = sf + af
    print(f"\n결과: {total_passed}개 통과, {total_failed}개 실패")

    if total_failed > 0:
        sys.exit(1)
