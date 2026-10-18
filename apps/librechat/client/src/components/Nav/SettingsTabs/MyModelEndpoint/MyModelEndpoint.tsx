// 封存 · pico#1349 (owner 2026-10-18「先下线功能，代码暂时不删除」): not mounted;
// the API answers 404 while app/model_endpoint.SEALED is True.
import { useEffect, useState } from 'react';
import {
  Label,
  Input,
  Button,
  Switch,
  Spinner,
  OGDialog,
  SecretInput,
  OGDialogTitle,
  OGDialogHeader,
  OGDialogFooter,
  InfoHoverCard,
  OGDialogTrigger,
  OGDialogContent,
} from '@librechat/client';
import useMyModelEndpoint from '~/hooks/Pico/useMyModelEndpoint';
import { useLocalize } from '~/hooks';

/** pico#1331「我的接口」: teacher's own OpenAI-compatible endpoint.
 *
 * Mirrors the ProviderKeys row (label + "管理" dialog) without touching that
 * component. Identity is always the signed-in teacher — there is no school
 * / membership field here for the teacher to edit.
 */
export default function MyModelEndpoint() {
  const localize = useLocalize();
  const [open, setOpen] = useState(false);
  const { data, loading, saving, testing, deleting, error, testResult, refresh, save, remove, test } =
    useMyModelEndpoint();

  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    if (!open) {
      return;
    }
    refresh();
  }, [open, refresh]);

  useEffect(() => {
    setBaseUrl(data.base_url || '');
    setModel(data.model || '');
    setEnabled(data.configured ? data.enabled : true);
    setApiKey('');
  }, [data]);

  const handleSave = async () => {
    const ok = await save({ base_url: baseUrl.trim(), model: model.trim(), api_key: apiKey.trim(), enabled });
    if (ok) {
      setApiKey('');
    }
  };

  const handleTest = async () => {
    await test({ base_url: baseUrl.trim(), model: model.trim(), api_key: apiKey.trim() });
  };

  const handleRemove = async () => {
    const ok = await remove();
    if (ok) {
      setBaseUrl('');
      setModel('');
      setApiKey('');
      setEnabled(true);
    }
  };

  return (
    <div className="flex items-center justify-between">
      <Label id="my-model-endpoint-label">
        {localize('com_ui_settings_label_my_model_endpoint')}
      </Label>
      <OGDialog open={open} onOpenChange={setOpen}>
        <OGDialogTrigger asChild>
          <Button variant="outline" aria-labelledby="my-model-endpoint-label">
            {localize('com_ui_manage')}
          </Button>
        </OGDialogTrigger>
        <OGDialogContent
          className="w-11/12 max-w-md bg-background text-text-primary shadow-2xl"
          aria-describedby={undefined}
        >
          <OGDialogHeader className="space-y-0 pr-8 text-left">
            <div className="flex items-center gap-1.5">
              <OGDialogTitle>
                {localize('com_ui_settings_label_my_model_endpoint')}
              </OGDialogTitle>
              <InfoHoverCard text={localize('com_ui_my_model_endpoint_description')} />
            </div>
          </OGDialogHeader>

          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label htmlFor="my-endpoint-base-url" className="text-sm font-medium">
                接口地址
              </Label>
              <Input
                id="my-endpoint-base-url"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.openai.com/v1"
                disabled={loading}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="my-endpoint-model" className="text-sm font-medium">
                模型名
              </Label>
              <Input
                id="my-endpoint-model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="gpt-4o-mini"
                disabled={loading}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="my-endpoint-key" className="text-sm font-medium">
                密钥
              </Label>
              <SecretInput
                id="my-endpoint-key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={data.masked_key ? data.masked_key : 'sk-…'}
                disabled={loading}
              />
              {data.masked_key && (
                <div className="text-xs text-text-secondary">
                  已保存：{data.masked_key}（留空密钥框 = 不换密钥）
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-1">
              <Label htmlFor="my-endpoint-enabled" className="text-sm font-medium">
                开启后这次对话用这个接口
              </Label>
              <Switch
                id="my-endpoint-enabled"
                checked={enabled}
                onCheckedChange={setEnabled}
                disabled={loading}
                aria-label="开启后这次对话用这个接口"
              />
            </div>

            {testResult && (
              <div
                className={`text-sm ${testResult.ok ? 'text-green-600' : 'text-red-500'}`}
                role="status"
              >
                {testResult.ok
                  ? `能用。${testResult.model ? `回了 ${testResult.model}，` : ''}用了 ${testResult.latency_ms ?? 0} 毫秒`
                  : testResult.reason || '测不通，原因不明'}
              </div>
            )}
            {error && (
              <div className="text-sm text-red-500" role="alert">
                {error}
              </div>
            )}
          </div>

          <OGDialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
            {data.configured ? (
              <Button variant="destructive" onClick={handleRemove} disabled={deleting}>
                {deleting ? <Spinner /> : '删除'}
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={handleTest} disabled={testing || loading}>
                {testing ? <Spinner /> : '测一下'}
              </Button>
              <Button variant="submit" onClick={handleSave} disabled={saving || loading}>
                {saving ? <Spinner /> : '保存'}
              </Button>
            </div>
          </OGDialogFooter>
        </OGDialogContent>
      </OGDialog>
    </div>
  );
}
