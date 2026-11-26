"""Exercise the LibreChat shortcut detectors with the runner's Node.js."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sandbox_open_intents() -> None:
    subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            r"""
            import assert from 'node:assert/strict';
            import { detectOpenWebsiteIntent, detectOpenOfficeIntent }
              from './apps/librechat/client/src/utils/picoOpenInPane.ts';

            assert.equal(detectOpenWebsiteIntent('打开 https://example.com。'), 'https://example.com/');
            assert.equal(detectOpenWebsiteIntent('打开浏览器'), 'https://example.com/');
            assert.equal(detectOpenWebsiteIntent('打开腾讯网'), 'https://www.qq.com/');
            assert.equal(detectOpenWebsiteIntent('你好'), null);

            for (const message of [
              '先读说明\n打开 https://example.com\n然后截图',
              '打开 https://example.com。没登录就停在登录页',
              '请先看 https://example.com，再打开 报告.docx',
              '打开 example.com 下载数据，再打开 成绩.xlsx',
            ]) {
              assert.equal(detectOpenWebsiteIntent(message), null, message);
              assert.equal(detectOpenOfficeIntent(message), null, message);
            }
            assert.deepEqual(detectOpenOfficeIntent('打开 备课-www.xlsx'), {
              kind: 'calc', filename: '备课-www.xlsx',
            });
            assert.deepEqual(detectOpenOfficeIntent('打开 Word'), { kind: 'writer' });
            """,
        ],
        cwd=ROOT,
        check=True,
    )
