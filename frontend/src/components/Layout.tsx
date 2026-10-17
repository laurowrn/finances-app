import {
  ArrowLeftRight,
  FileUp,
  HandCoins,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  PiggyBank,
  Settings,
  ShieldCheck,
  Sparkles,
  Tags,
  Wand2,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/lib/auth";

const NAV = [
  { to: "/", label: "Relatório", icon: LayoutDashboard, end: true },
  { to: "/ai", label: "Relatório IA", icon: Sparkles },
  { to: "/import", label: "Importar", icon: FileUp },
  { to: "/transactions", label: "Gastos", icon: ArrowLeftRight },
  { to: "/rules", label: "Regras", icon: Wand2 },
  { to: "/payments", label: "Pagamentos", icon: HandCoins },
  { to: "/categories", label: "Categorias", icon: Tags },
  { to: "/settings", label: "Configurações", icon: Settings },
];

export function Layout() {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  function closeMobile() {
    setMobileOpen(false);
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
      isActive
        ? "bg-indigo-50 text-indigo-700"
        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
    } ${collapsed ? "justify-center" : ""}`;

  return (
    <div className="h-screen overflow-hidden">
      {mobileOpen && (
        <button
          aria-label="Fechar menu"
          className="fixed inset-0 z-30 bg-gray-900/30 md:hidden"
          onClick={closeMobile}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex h-screen flex-col border-r border-gray-100 bg-white p-3 shadow-sm transition-[width,transform] duration-200 md:translate-x-0 md:shadow-none ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ width: collapsed ? "5rem" : "16rem" }}
      >
        <div className={`mb-6 flex items-center ${collapsed ? "justify-center" : "justify-between"}`}>
          <div className="flex min-w-0 items-center gap-2 px-2">
            <PiggyBank className="h-6 w-6 shrink-0 text-indigo-600" />
            {!collapsed && <span className="truncate font-semibold text-gray-900">Finanças do Casal</span>}
          </div>
          <button
            aria-label={collapsed ? "Expandir menu" : "Recolher menu"}
            title={collapsed ? "Expandir menu" : "Recolher menu"}
            className="hidden rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-900 md:block"
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
          </button>
          <button aria-label="Fechar menu" className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 md:hidden" onClick={closeMobile}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={linkClass} onClick={closeMobile} title={collapsed ? label : undefined}>
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
          {user?.is_admin && (
            <NavLink to="/admin" className={linkClass} onClick={closeMobile} title={collapsed ? "Administração" : undefined}>
              <ShieldCheck className="h-4 w-4 shrink-0" />
              {!collapsed && <span>Administração</span>}
            </NavLink>
          )}
        </nav>

        <div className="mt-3 border-t border-gray-100 pt-3">
          <div className={`mb-2 flex items-center gap-2 px-3 text-sm text-gray-500 ${collapsed ? "justify-center" : ""}`} title={collapsed ? user?.name : undefined}>
            <ListChecks className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="truncate">{user?.name}</span>}
          </div>
          <button
            onClick={logout}
            title={collapsed ? "Sair" : undefined}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 ${collapsed ? "justify-center" : ""}`}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Sair</span>}
          </button>
        </div>
      </aside>

      <main className={`h-full overflow-y-auto transition-[margin] duration-200 ${collapsed ? "md:ml-20" : "md:ml-64"}`}>
        <div className="flex items-center border-b border-gray-100 bg-white/90 px-4 py-3 backdrop-blur md:hidden">
          <button aria-label="Abrir menu" className="rounded-lg p-2 text-gray-600 hover:bg-gray-100" onClick={() => setMobileOpen(true)}>
            <Menu className="h-5 w-5" />
          </button>
          <span className="ml-3 font-semibold text-gray-900">Finanças do Casal</span>
        </div>
        <div className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
