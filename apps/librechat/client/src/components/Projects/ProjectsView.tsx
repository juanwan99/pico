import { useDeferredValue, useEffect, useId, useMemo, useState } from 'react';
import * as Ariakit from '@ariakit/react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowUpDown, Check, Folder, Plus, Search, Trash2 } from 'lucide-react';
import { Input, Button, Spinner, DropdownPopup, useMediaQuery } from '@librechat/client';
import type { TChatProject } from 'librechat-data-provider';
import type { MenuItemProps, RenderProp } from '~/common';
import OpenSidebar from '~/components/Chat/Menus/OpenSidebar';
import { useDeleteProjectMutation, useProjectsInfiniteQuery } from '~/data-provider';
import ProjectCreateDialog from './ProjectCreateDialog';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

type ProjectSort = 'name' | 'createdAt' | 'lastConversationAt';

function renderSortMenuItem(label: string, isSelected: boolean): RenderProp {
  return function SortMenuItem({ className, ...props }) {
    return (
      <div {...props} className={cn(className, 'justify-between gap-5')}>
        <span className="truncate">{label}</span>
        {isSelected ? (
          <Check className="h-4 w-4 shrink-0 text-text-primary" aria-hidden="true" />
        ) : (
          <span className="h-4 w-4 shrink-0" aria-hidden="true" />
        )}
      </div>
    );
  };
}

function formatActivity(project: TChatProject) {
  const value = project.lastConversationAt ?? project.updatedAt ?? project.createdAt;
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function ProjectsView() {
  const localize = useLocalize();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<ProjectSort>('lastConversationAt');
  const [isCreating, setIsCreating] = useState(searchParams.get('new') === '1');
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const sortMenuId = useId();
  const [isSortMenuOpen, setIsSortMenuOpen] = useState(false);
  const deferredSearch = useDeferredValue(search);
  const isSmallScreen = useMediaQuery('(max-width: 768px)');
  const deleteProject = useDeleteProjectMutation();

  const { data, fetchNextPage, isFetchingNextPage, isLoading } = useProjectsInfiniteQuery({
    search: deferredSearch || undefined,
    sortBy,
    sortDirection: sortBy === 'name' ? 'asc' : 'desc',
  });

  const projects = useMemo(() => data?.pages.flatMap((page) => page.projects) ?? [], [data?.pages]);
  const hasNextPage = data?.pages[data.pages.length - 1]?.nextCursor != null;
  const sortOptions = useMemo(
    () => [
      { value: 'lastConversationAt' as const, label: localize('com_ui_latest_activity') },
      { value: 'createdAt' as const, label: localize('com_ui_sort_created') },
      { value: 'name' as const, label: localize('com_ui_name') },
    ],
    [localize],
  );
  const selectedSortLabel =
    sortOptions.find((option) => option.value === sortBy)?.label ??
    localize('com_ui_latest_activity');
  const sortMenuItems = useMemo<MenuItemProps[]>(
    () =>
      sortOptions.map((option) => {
        const isSelected = sortBy === option.value;
        return {
          id: `project-sort-${option.value}`,
          ariaLabel: option.label,
          ariaChecked: isSelected,
          onClick: () => setSortBy(option.value),
          render: renderSortMenuItem(option.label, isSelected),
        };
      }),
    [sortBy, sortOptions],
  );

  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setIsCreating(true);
    }
  }, [searchParams]);

  const handleCreateDialogChange = (open: boolean) => {
    setIsCreating(open);
    if (!open && searchParams.get('new') === '1') {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete('new');
      setSearchParams(nextParams, { replace: true });
    }
  };

  return (
    <main className="flex h-full min-h-0 flex-col overflow-auto bg-[#fafafa] text-text-primary dark:bg-presentation" data-testid="projects-view">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-black/[0.06] bg-white px-4 dark:border-border-light dark:bg-surface-primary">
        <div className="flex min-w-0 items-center gap-2.5">
          {isSmallScreen ? <OpenSidebar /> : null}
          <h1 className="text-[15px] font-semibold text-[#1a1a1a] dark:text-text-primary">
            {localize('com_ui_projects')}
          </h1>
        </div>
        <Button type="button" variant="submit" size="sm" onClick={() => setIsCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          {localize('com_ui_new_project')}
        </Button>
      </div>

      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 px-4 py-5 md:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="rounded-full bg-surface-active-alt px-3 py-1.5 text-[12.5px] font-medium text-text-primary">
              {localize('com_ui_your_projects')}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden text-[12px] text-text-secondary sm:inline">
              {localize('com_ui_sort_by')}
            </span>
            <DropdownPopup
              portal={true}
              focusLoop={true}
              unmountOnHide={true}
              menuId={sortMenuId}
              isOpen={isSortMenuOpen}
              setIsOpen={setIsSortMenuOpen}
              className="z-[125] min-w-56"
              trigger={
                <Ariakit.MenuButton
                  aria-label={localize('com_ui_sort_projects_by')}
                  className={cn(
                    'inline-flex h-8 items-center justify-between gap-2 whitespace-nowrap rounded-lg border border-border-medium bg-surface-secondary px-2.5 text-[12.5px] font-medium text-text-primary transition-colors hover:bg-surface-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring-primary disabled:pointer-events-none disabled:opacity-50 sm:w-40',
                    isSortMenuOpen && 'bg-surface-hover text-text-primary',
                  )}
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <ArrowUpDown
                      className="h-4 w-4 shrink-0 text-text-secondary"
                      aria-hidden="true"
                    />
                    <span className="truncate">{selectedSortLabel}</span>
                  </span>
                </Ariakit.MenuButton>
              }
              items={sortMenuItems}
            />
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">{localize('com_ui_search_projects')}</span>
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary"
              aria-hidden="true"
            />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={localize('com_ui_search_projects')}
              className="border-border-medium bg-surface-secondary pl-9 text-text-primary placeholder:text-text-secondary focus-visible:ring-2 focus-visible:ring-ring-primary"
            />
          </label>
        </div>

        <ProjectCreateDialog
          open={isCreating}
          onOpenChange={handleCreateDialogChange}
          onCreated={(project) => navigate(`/projects/${project._id}`)}
        />

        {isLoading ? (
          <div className="flex flex-1 items-center justify-center">
            <Spinner className="text-text-primary" />
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {projects.map((project) => {
              const activity = formatActivity(project);
              const confirmingDelete = confirmingDeleteId === project._id;
              return (
                <article
                  key={project._id}
                  className={cn(
                    'group/project relative flex min-h-[7rem] flex-col rounded-lg border border-border-medium bg-surface-secondary p-4 text-left transition-colors',
                    'hover:border-border-heavy hover:bg-surface-tertiary',
                  )}
                >
                  <button
                    type="button"
                    className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring-primary"
                    onClick={() => navigate(`/projects/${project._id}`)}
                    aria-label={`打开项目 ${project.name}`}
                  />
                  <span className="pointer-events-none relative flex min-w-0 items-center gap-2 pr-8">
                    <Folder className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden="true" />
                    <span className="truncate text-base font-semibold text-text-primary">
                      {project.name}
                    </span>
                  </span>
                  {project.description ? (
                    <span className="pointer-events-none relative mt-2 line-clamp-2 text-sm leading-relaxed text-text-secondary">
                      {project.description}
                    </span>
                  ) : null}
                  <span className="pointer-events-none relative mt-auto flex items-center justify-between gap-2 pt-4 text-xs text-text-secondary">
                    <span>
                      {project.conversationCount === 1
                        ? localize('com_ui_project_chat_count_single')
                        : localize('com_ui_project_chat_count', {
                            count: project.conversationCount,
                          })}
                    </span>
                    {activity ? <span className="shrink-0 truncate">{activity}</span> : null}
                  </span>
                  {confirmingDelete ? (
                    <div className="absolute right-2 top-2 z-10 flex items-center gap-1 rounded-lg border border-border-medium bg-white p-1 shadow-sm dark:bg-surface-secondary">
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteError(null);
                          deleteProject.mutate(project._id, {
                            onSuccess: () => setConfirmingDeleteId(null),
                            onError: (error) =>
                              setDeleteError(
                                error instanceof Error ? error.message : '删除项目失败，请重试',
                              ),
                          });
                        }}
                        disabled={deleteProject.isLoading}
                        className="rounded-md bg-red-600 px-2 py-1 text-[11px] font-medium text-white disabled:opacity-50"
                      >
                        确认删除
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmingDeleteId(null)}
                        className="rounded-md px-2 py-1 text-[11px] text-text-secondary hover:bg-surface-hover"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setDeleteError(null);
                        setConfirmingDeleteId(project._id);
                      }}
                      className="absolute right-2 top-2 z-10 inline-flex h-7 w-7 items-center justify-center rounded-md text-text-secondary opacity-0 transition-opacity hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover/project:opacity-100"
                      aria-label={`删除项目 ${project.name}`}
                      title="删除项目"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        )}
        {deleteError ? (
          <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-[12px] text-red-700">
            {deleteError}
          </p>
        ) : null}

        {!isLoading && projects.length === 0 && (
          <div className="rounded-lg border border-border-medium bg-transparent py-16 text-center text-sm text-text-secondary">
            <p className="text-[13px] font-medium text-[#6b6b6b]">
              {localize('com_ui_no_projects')}
            </p>
            <button
              type="button"
              onClick={() => setIsCreating(true)}
              className="mt-3 rounded-lg bg-[#1a1a1a] px-3 py-2 text-[12.5px] font-medium text-white"
            >
              {localize('com_ui_new_project')}
            </button>
          </div>
        )}

        {hasNextPage && (
          <Button
            type="button"
            variant="outline"
            className="mx-auto"
            onClick={() => fetchNextPage()}
            disabled={isFetchingNextPage}
          >
            {isFetchingNextPage ? localize('com_ui_loading') : localize('com_ui_load_more')}
          </Button>
        )}
      </div>
    </main>
  );
}
