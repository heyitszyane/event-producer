// Tiny hover "i" hint for panel and card headers. Uses the native title
// tooltip so it stays dependency-free; aria-label carries the same text for
// screen readers.
export default function InfoHint({ text }: { text: string }) {
  return (
    <span className="info-hint" tabIndex={0} title={text} aria-label={text} role="note">
      i
    </span>
  )
}
