import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { TableColumn } from '@librechat/client';
import PicoListTable from './PicoListTable';

type Row = { id: string; score?: number; health: string; provider: string };
const rows: Row[] = [
  { id: 'Bravo', score: 12, health: '健康', provider: '甲' },
  { id: 'Missing', health: '未知', provider: '乙' },
  { id: 'Alpha', score: 2, health: '严重', provider: '甲' },
  { id: 'Charlie', score: 8, health: '健康', provider: '乙' },
];
const columns: TableColumn<Row, unknown>[] = [
  { accessorKey: 'id', header: '渠道', meta: { isRowHeader: true } },
  { accessorKey: 'score', header: '可用率' },
];
const filters = [
  { label: '健康档', value: (row: Row) => row.health },
  { label: '提供方', value: (row: Row) => row.provider },
];

function setup(data = rows) {
  render(<PicoListTable data={data} columns={columns} filters={filters} emptyState="暂无记录" />);
  return userEvent.setup();
}

const order = () => screen.getAllByRole('rowheader').map((cell) => cell.textContent);

it('sorts numerically by keyboard in both directions with missing values last and restores source order', async () => {
  const user = setup();
  const header = screen.getByRole('button', { name: /^可用率 column/ });
  header.focus();
  await user.keyboard('{Enter}');
  expect(order()).toEqual(['Alpha', 'Charlie', 'Bravo', 'Missing']);
  await user.keyboard(' ');
  expect(order()).toEqual(['Bravo', 'Charlie', 'Alpha', 'Missing']);
  await user.keyboard('{Enter}');
  expect(order()).toEqual(['Bravo', 'Missing', 'Alpha', 'Charlie']);
});

it('applies OR within columns and AND across columns, removing filters without clearing sort', async () => {
  const user = setup();
  await user.click(screen.getByRole('button', { name: /^渠道 column/ }));
  await user.click(screen.getByRole('button', { name: '筛选' }));
  for (const value of ['健康', '严重', '甲']) {
    await user.click(screen.getByRole('checkbox', { name: value }));
  }
  expect(order()).toEqual(['Alpha', 'Bravo']);
  await user.keyboard('{Escape}');
  await user.click(screen.getByRole('button', { name: '健康档：健康 ×' }));
  expect(order()).toEqual(['Alpha']);
  await user.click(screen.getByRole('button', { name: '筛选' }));
  await user.click(screen.getByRole('checkbox', { name: '甲' }));
  await user.click(screen.getByRole('checkbox', { name: '乙' }));
  await user.keyboard('{Escape}');
  expect(screen.getByText('暂无符合筛选的记录')).toBeInTheDocument();
  const clear = screen.getAllByRole('button', { name: '清除筛选' });
  expect(clear).toHaveLength(2);
  await user.click(clear[1]);
  expect(order()).toEqual(['Alpha', 'Bravo', 'Charlie', 'Missing']);
});

it('shows the supplied empty state when there are no records', () => {
  setup([]);
  expect(screen.getByText('暂无记录')).toBeInTheDocument();
  expect(screen.queryByText('暂无符合筛选的记录')).not.toBeInTheDocument();
});
