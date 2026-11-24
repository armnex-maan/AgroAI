import { ReactNode } from "react";
import { Icon } from "./Icon";

export function PageHeader({ icon, title, subtitle, children, tone = "green" }: {
  icon: string; title: string; subtitle?: ReactNode; children?: ReactNode; tone?: "green" | "sky" | "amber" | "violet";
}) {
  return (
    <div className="page-head">
      <div className={`page-icon tone-${tone}`}><Icon name={icon} size={22} stroke={2} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children && <div className="row">{children}</div>}
    </div>
  );
}

export function Empty({ icon = "info", title, text, action }: { icon?: string; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon name={icon} size={22} /></div>
      <div className="empty-title">{title}</div>
      {text && <div className="empty-text">{text}</div>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  );
}

export function Help({ text }: { text: string }) {
  return <span className="help" title={text} aria-label={text}>?</span>;
}

export function Steps({ items }: { items: ReactNode[] }) {
  return (
    <ol className="steps">
      {items.map((it, i) => <li key={i}><span className="step-n">{i + 1}</span><div>{it}</div></li>)}
    </ol>
  );
}
