import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import {
  Login,
  VerifyEmail,
  Registration,
  ResetPassword,
  ApiErrorWatcher,
  TwoFactorScreen,
  RequestPasswordReset,
} from '~/components/Auth';
import { AuthContextProvider } from '~/hooks/AuthContext';
import WithRum from '~/lib/rum/WithRum';
import RouteErrorBoundary from './RouteErrorBoundary';
import StartupLayout from './Layouts/Startup';
import LoginLayout from './Layouts/Login';
import dashboardRoutes from './Dashboard';

const AuthLayout = () => (
  <AuthContextProvider>
    <WithRum>
      <Outlet />
    </WithRum>
    <ApiErrorWatcher />
  </AuthContextProvider>
);

const loadInlinePromptsView = () =>
  import('~/components/Prompts/layouts/InlinePromptsView').then((m) => ({
    Component: m.default,
  }));

const loadSkillsView = () =>
  import('~/components/Skills/layouts/SkillsView').then((m) => ({
    Component: m.default,
  }));

const loadProjectsView = () =>
  import('~/components/Projects').then((m) => ({
    Component: m.ProjectsView,
  }));

const loadProjectWorkspace = () =>
  import('~/components/Projects').then((m) => ({
    Component: m.ProjectWorkspace,
  }));

const loadAgentMarketplace = () =>
  Promise.all([
    import('~/components/Agents/Marketplace'),
    import('~/components/Agents/MarketplaceContext'),
  ]).then(([market, ctx]) => {
    function AgentMarketplaceRoute() {
      return (
        <ctx.MarketplaceProvider>
          <market.default />
        </ctx.MarketplaceProvider>
      );
    }
    return { Component: AgentMarketplaceRoute };
  });

const loadCapabilityHub = () =>
  import('~/components/Workbench/CapabilityHubPage').then((m) => ({
    Component: m.default,
  }));

const loadConnectorDetail = () =>
  import('~/components/Workbench/ConnectorDetailPage').then((m) => ({
    Component: m.default,
  }));

const loadAssistantPage = () =>
  import('~/components/Workbench/AssistantPage').then((m) => ({
    Component: m.default,
  }));

const loadAutomationPage = () =>
  import('~/components/Workbench/AutomationPage').then((m) => ({
    Component: m.default,
  }));

const loadMoreHub = () =>
  import('~/components/Workbench/MoreHubPage').then((m) => ({
    Component: m.default,
  }));

const loadFilesHub = () =>
  import('~/components/Workbench/FilesHubPage').then((m) => ({
    Component: m.default,
  }));

const loadWorkspaceHub = () =>
  import('~/components/Workbench/WorkspaceHubPage').then((m) => ({
    Component: m.default,
  }));

const loadShareRoute = () =>
  import('./ShareRoute').then((m) => ({
    Component: m.default,
  }));

const loadOAuthSuccess = () =>
  import('~/components/OAuth/OAuthSuccess').then((m) => ({
    Component: m.default,
  }));

const loadOAuthError = () =>
  import('~/components/OAuth/OAuthError').then((m) => ({
    Component: m.default,
  }));

const loadRoot = () =>
  import('./Root').then((m) => ({
    Component: m.default,
  }));

const loadChatRoute = () =>
  import('./ChatRoute').then((m) => ({
    Component: m.default,
  }));

const loadSearch = () =>
  import('./Search').then((m) => ({
    Component: m.default,
  }));

const baseEl = document.querySelector('base');
const baseHref = baseEl?.getAttribute('href') || '/';

export const router = createBrowserRouter(
  [
    {
      path: 'share/:shareId',
      lazy: loadShareRoute,
      errorElement: <RouteErrorBoundary />,
    },
    {
      path: 'oauth',
      errorElement: <RouteErrorBoundary />,
      children: [
        {
          path: 'success',
          lazy: loadOAuthSuccess,
        },
        {
          path: 'error',
          lazy: loadOAuthError,
        },
      ],
    },
    {
      path: '/',
      element: <StartupLayout />,
      errorElement: <RouteErrorBoundary />,
      children: [
        {
          path: 'register',
          element: <Registration />,
        },
        {
          path: 'forgot-password',
          element: <RequestPasswordReset />,
        },
        {
          path: 'reset-password',
          element: <ResetPassword />,
        },
      ],
    },
    {
      path: 'verify',
      element: <VerifyEmail />,
      errorElement: <RouteErrorBoundary />,
    },
    {
      element: <AuthLayout />,
      errorElement: <RouteErrorBoundary />,
      children: [
        {
          path: '/',
          element: <LoginLayout />,
          children: [
            {
              path: 'login',
              element: <Login />,
            },
            {
              path: 'login/2fa',
              element: <TwoFactorScreen />,
            },
          ],
        },
        dashboardRoutes,
        {
          path: '/',
          lazy: loadRoot,
          children: [
            {
              index: true,
              element: <Navigate to="/c/new" replace={true} />,
            },
            {
              path: 'c/:conversationId?',
              lazy: loadChatRoute,
            },
            {
              path: 'search',
              lazy: loadSearch,
            },
            {
              path: 'prompts',
              element: <Navigate to="/prompts/new" replace={true} />,
            },
            {
              path: 'prompts/new',
              lazy: loadInlinePromptsView,
            },
            {
              path: 'prompts/:promptId',
              lazy: loadInlinePromptsView,
            },
            {
              path: 'skills',
              lazy: loadSkillsView,
            },
            {
              path: 'skills/new',
              lazy: loadSkillsView,
            },
            {
              path: 'skills/:skillId',
              lazy: loadSkillsView,
            },
            {
              path: 'skills/:skillId/edit',
              lazy: loadSkillsView,
            },
            {
              path: 'projects',
              lazy: loadProjectsView,
            },
            {
              path: 'projects/:projectId',
              lazy: loadProjectWorkspace,
            },
            {
              path: 'agents',
              lazy: loadAgentMarketplace,
            },
            {
              path: 'agents/:category',
              lazy: loadAgentMarketplace,
            },
            {
              path: 'assistants',
              lazy: loadAssistantPage,
            },
            {
              path: 'capability',
              lazy: loadCapabilityHub,
            },
            {
              path: 'capability/connectors/:connectorId',
              lazy: loadConnectorDetail,
            },
            {
              path: 'skills/manage',
              lazy: loadSkillsView,
            },
            {
              path: 'automation',
              lazy: loadAutomationPage,
            },
            {
              path: 'more',
              lazy: loadMoreHub,
            },
            {
              path: 'more/files',
              lazy: loadFilesHub,
            },
            {
              path: 'workspaces',
              lazy: loadWorkspaceHub,
            },
          ],
        },
      ],
    },
  ],
  { basename: baseHref },
);
