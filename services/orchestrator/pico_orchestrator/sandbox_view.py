"""Teacher-facing B2 view HTML. Passwords never appear in this markup."""

from __future__ import annotations

import html as html_lib

LOGIN_COPY = "请在此画面自行登录，不要在聊天里发送密码"


def render_session_view_html(
    *,
    session_id: str,
    screenshot_path: str,
    page_url: str,
    workspace_id: str,
    input_path: str,
) -> str:
    sid = html_lib.escape(session_id)
    shot = html_lib.escape(screenshot_path)
    url = html_lib.escape(page_url)
    ws = html_lib.escape(workspace_id)
    action = html_lib.escape(input_path)
    copy = html_lib.escape(LOGIN_COPY)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Pico 隔离登录画面</title>
  <style>
    body {{ font-family: sans-serif; margin: 0; background: #111; color: #eee; }}
    .banner {{ background: #1f4e3d; color: #fff; padding: 12px 16px; font-size: 16px; }}
    .meta {{ padding: 8px 16px; color: #bbb; font-size: 13px; }}
    img {{ display: block; width: min(100%, 1280px); background: #fff; cursor: crosshair; }}
    form {{ padding: 12px 16px 24px; }}
    input[type=text], input[type=password] {{ padding: 8px; width: min(100%, 320px); }}
    button {{ margin-top: 8px; padding: 8px 12px; }}
  </style>
</head>
<body>
  <div class="banner">{copy}</div>
  <div class="meta">session={sid} · workspace={ws} · url={url}<br/>
  画面来自 sidecar Chromium viewport。点图即点击页面。会话随沙箱销毁，Cookie 不会写回宿主机。微信/教务不是过关条件。</div>
  <img id="viewport" src="{shot}" alt="isolated chromium viewport" width="1280"/>
  <form id="input-form" method="post" action="{action}" autocomplete="off">
    <p>在此画面自行点击/输入。不要把密码发到聊天。</p>
    <div>
      <label>点击 x <input type="number" name="click_x" id="click_x" /></label>
      <label>y <input type="number" name="click_y" id="click_y" /></label>
    </div>
    <div>
      <label>可见输入 <input type="text" name="text" autocomplete="off"/></label>
    </div>
    <div>
      <label>密码（仅进隔离会话） <input type="password" name="secret" autocomplete="new-password"/></label>
    </div>
    <button type="submit">送到 sidecar Chromium</button>
  </form>
  <script>
    (function () {{
      var img = document.getElementById("viewport");
      var form = document.getElementById("input-form");
      if (!img || !form) return;
      img.addEventListener("click", function (ev) {{
        var rect = img.getBoundingClientRect();
        var nw = img.naturalWidth || 1280;
        var nh = img.naturalHeight || 800;
        var x = Math.round((ev.clientX - rect.left) * (nw / rect.width));
        var y = Math.round((ev.clientY - rect.top) * (nh / rect.height));
        var fd = new FormData();
        fd.set("click_x", String(x));
        fd.set("click_y", String(y));
        fetch(form.action, {{ method: "POST", body: fd, credentials: "same-origin", redirect: "follow" }})
          .then(function () {{ window.location.reload(); }})
          .catch(function () {{ window.location.reload(); }});
      }});
    }})();
  </script>
</body>
</html>
"""
