"""Fixed Prime Numbers remote checks, always within an Adapter-owned session."""
import json
import re


def check_primes(adapter):
    def log():
        pid = adapter.shell('pidof', adapter.package).strip()
        return adapter.adb('logcat', '-d', '--pid=' + pid, '-v', 'brief')

    def selected():
        data = log()
        (adapter.out/'navigation-logcat.txt').write_text(data)
        values = re.findall(r'PRIME_FOCUS (\d+) grid', data)
        if not values:
            raise RuntimeError('No visible chart navigation was reported')
        return int(values[-1])

    def tap(code, count=1):
        for _ in range(count):
            adapter.key('KEYCODE_' + code)

    def capture(name):
        adapter.wait(.25)
        adapter.capture(name + '-')

    assertions = []
    capture('study')
    tap('DPAD_CENTER'); capture('study-reference')
    if 'PRIME_STUDY_REFERENCE' not in log():
        raise RuntimeError('Study reference action was not confirmed')
    # Move to the middle, leaving room to exercise all held directions.
    tap('DPAD_DOWN', 4); tap('DPAD_RIGHT', 4)
    actual = selected()
    if actual != 45:
        raise RuntimeError('Chart navigation reached '+str(actual)+' instead of 45')
    for direction, sign, step in [('UP', -1, 10), ('DOWN', 1, 10), ('LEFT', -1, 1), ('RIGHT', 1, 1)]:
        before = selected()
        adapter.shell('input', 'keyevent', '--longpress', 'KEYCODE_DPAD_' + direction)
        adapter.wait(.15)
        after = selected()
        if (after - before) * sign <= 0 or (after - before) % step:
            raise RuntimeError('Held ' + direction + ' did not move correctly')
        adapter.wait(.6)
        if selected() != after:
            raise RuntimeError('Direction remained held after release: ' + direction)
        capture('released-' + direction.lower())
        assertions.append({'direction': direction, 'before': before, 'after': after, 'released': True})
    # Recall marks numbers directly, with no per-number question or feedback.
    adapter.launch()
    tap('DPAD_UP'); tap('DPAD_RIGHT'); tap('DPAD_CENTER')
    capture('recall-hidden')
    tap('DPAD_CENTER'); tap('DPAD_CENTER')  # Mark then unmark 1.
    capture('recall-unmarked')
    tap('DPAD_RIGHT'); tap('DPAD_CENTER')  # Mark 2, then 3, with no prompt.
    tap('DPAD_RIGHT'); tap('DPAD_CENTER')
    capture('recall-marked')
    tap('DPAD_UP'); tap('DPAD_RIGHT'); tap('DPAD_CENTER')  # Check marks.
    capture('recall-results')
    observed = log()
    for marker in ('PRIME_MODE recall', 'PRIME_MARK 1 on', 'PRIME_MARK 1 off', 'PRIME_MARK 2 on', 'PRIME_MARK 3 on', 'PRIME_CHECK 2 correct 0 wrong 23 missing'):
        if marker not in observed:
            raise RuntimeError('Missing recall evidence: ' + marker)
    tap('BACK'); tap('BACK')  # results -> Recall grid -> Study grid
    initial = adapter.shell('pidof', adapter.package).strip()
    tap('HOME'); adapter.wait(.8)
    adapter.shell('am', 'start', '-n', adapter.activity()); adapter.wait(1)
    adapter.require_foreground()
    if adapter.shell('pidof', adapter.package).strip() != initial:
        raise RuntimeError('Home/resume changed process')
    capture('resumed')
    before = selected(); adapter.wait(.6)
    if selected() != before:
        raise RuntimeError('Chart moved after lifecycle resume')
    # Base Study Back must exit rather than trapping the user in the app.
    tap('BACK'); adapter.wait(.5)
    if any(adapter.package + '/' in line for line in adapter.foreground()):
        raise RuntimeError('Base Study Back did not exit the app')
    adapter.launch(); capture('final-study')
    (adapter.out/'prime-assertions.json').write_text(json.dumps({
        'directions': assertions, 'reference_only_study': 'PASS', 'recall': 'PASS',
        'home_resume': 'PASS', 'back_exit': 'PASS'}, indent=2) + '\n')
