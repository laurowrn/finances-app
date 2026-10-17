import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { Card } from "@/components/ui";
import { formatBRL, type Settlement } from "@/lib/api";

export function SettlementCard({
  title,
  settlement,
  action,
  hint,
}: {
  title: string;
  settlement: Settlement;
  action?: ReactNode;
  hint?: string;
}) {
  if (!settlement.amount_cents || !settlement.from_user_name) {
    return (
      <Card className="bg-emerald-50">
        <p className="text-center text-sm font-medium text-emerald-700">
          Tudo certo — ninguém deve nada. 🎉
        </p>
      </Card>
    );
  }
  return (
    <Card className="border-indigo-100 bg-gradient-to-br from-indigo-50 to-white">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-medium text-gray-500">{title}</p>
        {action}
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3 text-center">
        <span className="text-lg font-semibold text-gray-900">{settlement.from_user_name}</span>
        <span className="flex items-center gap-2 rounded-full bg-indigo-600 px-4 py-1.5 text-lg font-bold text-white">
          {formatBRL(settlement.amount_cents)}
          <ArrowRight className="h-5 w-5" />
        </span>
        <span className="text-lg font-semibold text-gray-900">{settlement.to_user_name}</span>
      </div>
      {hint && <p className="mt-3 text-center text-xs text-gray-400">{hint}</p>}
    </Card>
  );
}
