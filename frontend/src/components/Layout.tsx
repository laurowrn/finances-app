import {
  ArrowLeftRight,
  FileUp,
  HandCoins,
  LayoutDashboard,
  ListChecks,
  LogOut,
  PiggyBank,
  Settings,
  Tags,
  Wand2,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "@/lib/auth";

const NAV = [
  { to: "/", label: "Relatório", icon: LayoutDashboard, end: true },
  { to: "/import", label: "Importar", icon: FileUp },
  { to: "/transactions", label: "Gastos", icon: ArrowLeftRight },
  { to: "/rules", label: "Regras", icon: Wand2 },
  { to: "/payments", label: "Pagamentos", icon: HandCoins },
  { to: "/categories", label: "Categorias", icon: Tags },
  { to: "/settings", label: "Configurações", icon: Settings },
];

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r border-gray-100 bg-white p-4">
        <div className="mb-6 flex items-center gap-2 px-2">
          <PiggyBank className="h-6 w-6 text-indigo-600" />
          <span className="font-semibold text-gray-900">Finanças do Casal</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-4 border-t border-gray-100 pt-4">
          <div className="mb-2 flex items-center gap-2 px-3 text-sm text-gray-500">
            <ListChecks className="h-4 w-4" />
            {user?.name}
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
          >
            <LogOut className="h-4 w-4" />
            Sair
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8">
        <div className="mx-auto max-w-5xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
