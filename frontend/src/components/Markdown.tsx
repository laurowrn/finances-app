import { type ReactNode } from "react";

/**
 * Renderizador de markdown mínimo, só o que o relatório de IA usa:
 * títulos, listas, tabelas, citação, negrito, itálico e código inline.
 *
 * Escrito à mão em vez de puxar uma dependência porque o conteúdo tem uma
 * origem só (a skill) e o conjunto de marcações é fechado. O texto NUNCA é
 * inserido como HTML — cada pedaço vira elemento React, então não há caminho
 * para injeção mesmo que o markdown venha malformado.
 */
export function Markdown({ source }: { source: string }) {
  return <div className="flex flex-col gap-3">{parseBlocks(source)}</div>;
}

function parseBlocks(source: string): ReactNode[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i++;
      continue;
    }

    // Tabela: linha com | seguida da linha de separação |---|
    if (line.includes("|") && lines[i + 1]?.match(/^\s*\|?[\s:|-]+\|[\s:|-]*$/)) {
      const header = splitRow(line);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
        rows.push(splitRow(lines[i]));
        i++;
      }
      out.push(<Table key={key++} header={header} rows={rows} />);
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      out.push(<Heading key={key++} level={heading[1].length} text={heading[2]} />);
      i++;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        quote.push(lines[i].replace(/^\s*>\s?/, ""));
        i++;
      }
      out.push(
        <blockquote
          key={key++}
          className="border-l-4 border-indigo-200 bg-indigo-50/40 py-2 pl-4 text-sm text-gray-700"
        >
          {inline(quote.join(" "))}
        </blockquote>,
      );
      continue;
    }

    const bullet = /^\s*[-*]\s+/;
    const numbered = /^\s*\d+\.\s+/;
    if (bullet.test(line) || numbered.test(line)) {
      const ordered = numbered.test(line);
      const re = ordered ? numbered : bullet;
      const items: string[] = [];
      while (i < lines.length && re.test(lines[i])) {
        items.push(lines[i].replace(re, ""));
        i++;
      }
      const List = ordered ? "ol" : "ul";
      out.push(
        <List
          key={key++}
          className={`ml-5 flex flex-col gap-1 text-sm text-gray-700 ${
            ordered ? "list-decimal" : "list-disc"
          }`}
        >
          {items.map((it, n) => (
            <li key={n}>{inline(it)}</li>
          ))}
        </List>,
      );
      continue;
    }

    if (/^\s*(---|\*\*\*)\s*$/.test(line)) {
      out.push(<hr key={key++} className="border-gray-100" />);
      i++;
      continue;
    }

    // Parágrafo: junta linhas até a próxima em branco.
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^\s*([-*>#]|\d+\.)\s/.test(lines[i])) {
      para.push(lines[i]);
      i++;
    }
    out.push(
      <p key={key++} className="text-sm leading-relaxed text-gray-700">
        {inline(para.join(" "))}
      </p>,
    );
  }

  return out;
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());
}

function Heading({ level, text }: { level: number; text: string }) {
  const cls =
    level === 1
      ? "text-lg font-semibold text-gray-900"
      : level === 2
        ? "mt-2 text-base font-semibold text-gray-900"
        : "mt-1 text-sm font-semibold text-gray-700";
  return <p className={cls}>{inline(text)}</p>;
}

function Table({ header, rows }: { header: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b border-gray-100 bg-gray-50 text-left text-xs uppercase text-gray-500">
          <tr>
            {header.map((h, i) => (
              <th key={i} className={`px-3 py-2 ${i > 0 ? "text-right" : ""}`}>
                {inline(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-gray-50">
              {r.map((c, j) => (
                <td
                  key={j}
                  className={`px-3 py-1.5 text-gray-700 ${j > 0 ? "text-right" : ""}`}
                >
                  {inline(c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** `**negrito**`, `*itálico*` e `` `código` `` — em elementos, nunca em HTML. */
function inline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;

  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const token = m[0];
    if (token.startsWith("**")) {
      parts.push(
        <strong key={key++} className="font-semibold text-gray-900">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("`")) {
      parts.push(
        <code key={key++} className="rounded bg-gray-100 px-1 py-0.5 text-xs text-gray-800">
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      parts.push(<em key={key++}>{token.slice(1, -1)}</em>);
    }
    last = m.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
