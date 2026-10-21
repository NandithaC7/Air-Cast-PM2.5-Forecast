export function FieldList({ items }: { items: { label: string; value: string }[] }) {
  return (
    <dl className="fields">
      {items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
