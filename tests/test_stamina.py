from game_core.models import Player
from game_core.stamina import settle_stamina

REGEN_MIN = 5      # 每 5 分钟回 1
MAX = 50
STEP = 5 * 60      # 5 分钟的秒数


def _player(stamina, stamina_at):
    return Player(group_id="g", user_id="u", name="勇者",
                  stamina=stamina, stamina_at=stamina_at)


def test_no_time_passed_no_regen():
    p = _player(10, 1000)
    settle_stamina(p, now=1000, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 10
    assert p.stamina_at == 1000


def test_partial_regen():
    p = _player(10, 1000)
    # 过了 17 分钟 → 回 3 点(整除),余 2 分钟保留
    settle_stamina(p, now=1000 + 17 * 60, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 13
    # 时间戳推进 15 分钟(已兑现的 3 点),不是 17 分钟
    assert p.stamina_at == 1000 + 15 * 60


def test_caps_at_max_and_resets_timestamp():
    p = _player(48, 1000)
    # 过很久 → 应封顶在 50,且时间戳拉到 now
    now = 1000 + 999 * 60
    settle_stamina(p, now=now, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == MAX
    assert p.stamina_at == now


def test_remainder_not_lost_across_calls():
    p = _player(0, 1000)
    # 第一次:7 分钟 → 回 1,余 2 分钟
    settle_stamina(p, now=1000 + 7 * 60, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 1
    # 第二次:再过 3 分钟(累计余 2+3=5)→ 再回 1
    settle_stamina(p, now=1000 + 10 * 60, regen_minutes=REGEN_MIN, max_stamina=MAX)
    assert p.stamina == 2


def test_regen_amount_multiplies():
    # regen_minutes=1, regen_amount=10 → 每分钟回 10 点
    p = _player(0, 1000)
    settle_stamina(p, now=1000 + 3 * 60, regen_minutes=1,
                   max_stamina=100, regen_amount=10)
    assert p.stamina == 30          # 3 分钟 × 10


def test_regen_amount_respects_cap():
    p = _player(0, 1000)
    settle_stamina(p, now=1000 + 10 * 60, regen_minutes=1,
                   max_stamina=50, regen_amount=10)
    assert p.stamina == 50          # 100 应被封顶到 50
