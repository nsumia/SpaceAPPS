/** Small "?" help bubble: hover, keyboard focus or tap shows the explanation (also exposed as aria-label / title). */
export function Info({ text, label = "?" }: { text: string; label?: string }) {
  return <span className="info" tabIndex={0} role="note" aria-label={text} title={text} data-tip={text}>{label}</span>;
}
