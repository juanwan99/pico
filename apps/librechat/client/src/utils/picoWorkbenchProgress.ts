/** Chinese in-flight / done / fail lines for workbench tools. No fake percentages. */

const DOING: Record<string, string> = {
  generate_html_document: '正在写网页',
  generate_docx_document: '正在写 Word',
  generate_pptx_document: '正在写 PPT',
  generate_xlsx_document: '正在写表格',
  edit_docx_document: '正在改 Word',
  edit_pptx_document: '正在改 PPT',
  edit_xlsx_document: '正在改表格',
  render_document: '正在排文档',
  inspect_document: '正在读文档结构',
  verify_document: '正在核对文档',
  generate_image: '正在出图',
  workspace_write_file: '正在落盘',
  workspace_list_files: '正在列文件',
  workspace_read_file: '正在读文件',
  verify_html_document: '正在核对网页',
  web_search: '正在检索',
  web_fetch: '正在阅读网页',
};

const DONE: Record<string, string> = {
  generate_html_document: '已写网页',
  generate_docx_document: '已写 Word',
  generate_pptx_document: '已写 PPT',
  generate_xlsx_document: '已写表格',
  edit_docx_document: '已改 Word',
  edit_pptx_document: '已改 PPT',
  edit_xlsx_document: '已改表格',
  render_document: '已排文档',
  inspect_document: '已读文档结构',
  verify_document: '已核对文档',
  generate_image: '已出图',
  workspace_write_file: '已落盘',
  workspace_list_files: '已列文件',
  workspace_read_file: '已读文件',
  verify_html_document: '已核对网页',
  web_search: '已检索到来源',
  web_fetch: '已读页',
};

const FAIL: Record<string, string> = {
  generate_html_document: '没写成网页',
  generate_docx_document: '没写成 Word',
  generate_pptx_document: '没写成 PPT',
  generate_xlsx_document: '没写成表格',
  edit_docx_document: '没改成 Word',
  edit_pptx_document: '没改成 PPT',
  edit_xlsx_document: '没改成表格',
  render_document: '没排成文档',
  inspect_document: '没读成文档结构',
  verify_document: '文档核对未完成',
  generate_image: '没出成图',
  workspace_write_file: '没落成盘',
  workspace_list_files: '没列出文件',
  workspace_read_file: '没读成文件',
  verify_html_document: '网页核对未完成',
  web_search: '检索未完成',
  web_fetch: '读页未完成',
};

export function workbenchToolStepLine(tool: string): string {
  const name = tool.trim();
  if (!name) {
    return '';
  }
  return DOING[name] ?? '正在调工具';
}

export function workbenchToolResultLine(tool: string, ok: boolean): string {
  const name = tool.trim();
  if (!name) {
    return ok ? '工具已完成' : '工具没完成';
  }
  const table = ok ? DONE : FAIL;
  return table[name] ?? (ok ? '工具已完成' : '工具没完成');
}
