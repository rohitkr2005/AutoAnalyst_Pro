import urllib.request

def check(url, name, tokens):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode('utf-8')
        for t in tokens:
            if t not in content:
                print(f'[FAIL] In {name}, missing {t}')
                print(f'Content length: {len(content)}')
                print(f'Content snippet: {content[:300]}')
            assert t in content, f'Missing {t} in {name}'
        print(f'[PASS] {name}: all {len(tokens)} tokens verified')

check('http://localhost:5000/login', 'Login Page', [
    'id="bg-3d-canvas"',
    'theme-switch-control',
    "setThemeMode('light')",
    "setThemeMode('dark')",
    "setThemeMode('system')",
    '/static/js/theme-3d.js',
    'data-theme-pref'
])

check('http://localhost:5000/static/js/theme-3d.js', 'Theme-3D Script', [
    'ThemeManager',
    'Live3DBackground',
    'setThemeMode',
    'project3D',
    'createIcosahedron',
    'createOctahedron',
    'analytica_theme_pref'
])

check('http://localhost:5000/static/css/style.css', 'Stylesheets', [
    '[data-theme="light"]',
    '[data-theme="dark"]',
    '.bg-3d-canvas',
    '.theme-switch-control',
    '.theme-btn.active'
])

# Check protected / dashboard with demo session
import http.cookiejar
import json

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login as demo analyst
login_req = urllib.request.Request(
    'http://localhost:5000/api/auth/login',
    data=json.dumps({'username': 'admin', 'password': 'Password123!'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
resp = opener.open(login_req)
assert resp.status == 200, 'Login failed'

# Now fetch /
dash_resp = opener.open('http://localhost:5000/')
dash_content = dash_resp.read().decode('utf-8')
dash_tokens = [
    'id="bg-3d-canvas"',
    'theme-switch-control',
    "setThemeMode('light')",
    "setThemeMode('dark')",
    "setThemeMode('system')",
    '/static/js/theme-3d.js',
    'app-shell',
    'app-topbar'
]
for t in dash_tokens:
    assert t in dash_content, f'Missing {t} in Main Dashboard'
print(f'[PASS] Main Dashboard (GET /): all {len(dash_tokens)} tokens verified')

print('=== ALL FRONTEND ASSETS, AUTH, AND HTML VERIFIED 100% ===')
