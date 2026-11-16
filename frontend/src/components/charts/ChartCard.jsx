/**
 * Chart container: the title is the question the chart answers, and every chart has a table twin
 * so no value depends on hovering or on telling colors apart.
 */
import { useState } from 'react';
import { ChartLine, Table2 } from 'lucide-react';

export function DataTable({ columns, rows, caption }) {
  return (
    <div className="max-h-80 overflow-auto" tabIndex={0} role="region" aria-label={`${caption} table`}>
      <table className="table-data w-full text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 bg-surface">
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col" className={column.align === 'right' ? 'text-right' : ''}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.key ?? index}>
              {columns.map((column) => (
                <td key={column.key} className={column.align === 'right' ? 'text-right' : ''}>
                  {row[column.key] ?? '–'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ChartCard({ title, subtitle, table, legend, children, className = '' }) {
  const [view, setView] = useState('chart');
  const showTable = view === 'table';
  return (
    <figure className={`card m-0 flex min-w-0 flex-col p-4 sm:p-5 ${className}`}>
      <figcaption className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-lg font-bold">{title}</h3>
          {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
        </div>
        {table && (
          <button
            type="button"
            onClick={() => setView(showTable ? 'chart' : 'table')}
            aria-label={showTable ? `Show ${title} as a chart` : `Show ${title} as a table`}
            className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-line text-ink-muted transition-colors hover:border-line-strong hover:text-ink"
          >
            {showTable ? <ChartLine aria-hidden="true" className="size-[1.125rem]" /> : <Table2 aria-hidden="true" className="size-[1.125rem]" />}
          </button>
        )}
      </figcaption>
      {showTable ? (
        <DataTable caption={title} columns={table.columns} rows={table.rows} />
      ) : (
        <>
          {legend}
          {children}
        </>
      )}
    </figure>
  );
}

/** Legend entries mirror the mark: a short stroke for lines, a block for bars and areas. */
export function LegendRow({ items }) {
  return (
    <ul className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs font-medium text-ink-soft">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={item.kind === 'block' ? 'size-2.5 rounded-sm' : 'h-0.5 w-3.5 rounded-full'}
            style={{ background: item.color }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

/** Tooltip body shared by all Recharts charts. The value leads, and the series name follows. */
export function ChartTooltip({ active, payload, label, labelFormatter, valueFormatter, extra }) {
  if (!active || !payload?.length) return null;
  const heading = labelFormatter ? labelFormatter(label, payload) : label;
  return (
    <div className="max-w-60 rounded-lg border border-line-strong bg-overlay px-3 py-2 text-xs shadow-lg shadow-black/40">
      {heading && <p className="mb-1 text-ink-muted">{heading}</p>}
      <ul className="flex flex-col gap-0.5">
        {payload.map((entry) => {
          const color = entry.color || entry.stroke || entry.fill || entry.payload?.fill;
          return (
            <li key={entry.dataKey ?? entry.name} className="flex items-center gap-2">
              <span aria-hidden="true" className="h-0.5 w-3 shrink-0 rounded-full" style={{ background: color }} />
              <span className="font-semibold tabular-nums text-ink">
                {valueFormatter ? valueFormatter(entry.value, entry) : entry.value}
              </span>
              <span className="truncate text-ink-soft">{entry.name}</span>
            </li>
          );
        })}
      </ul>
      {extra && <div className="mt-1 text-ink-muted">{extra(payload)}</div>}
    </div>
  );
}
