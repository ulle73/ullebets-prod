export interface FilterOption {
  value: string;
  label: string;
}

export interface WorkflowFilter {
  key: string;
  label: string;
  value: string;
  options: FilterOption[];
}

interface WorkflowFiltersProps {
  filters: WorkflowFilter[];
  pageLimit: number;
  onFilterChange: (key: string, value: string) => void;
  onPageLimitChange: (value: number) => void;
}

function optionsWithCurrent(options: FilterOption[], value: string): FilterOption[] {
  if (!value || options.some((option) => option.value === value)) return options;
  return [...options, { value, label: value }];
}

export function WorkflowFilters({ filters, pageLimit, onFilterChange, onPageLimitChange }: WorkflowFiltersProps) {
  return (
    <section className="workflow-toolbar" aria-label="Filter">
      {filters.map((filter) => (
        <label className="workflow-filter" key={filter.key}>
          <span>{filter.label}</span>
          <select aria-label={filter.label} value={filter.value} onChange={(event) => onFilterChange(filter.key, event.target.value)}>
            {optionsWithCurrent(filter.options, filter.value).map((option) => <option value={option.value} key={option.value || 'all'}>{option.label}</option>)}
          </select>
        </label>
      ))}
      <label className="workflow-filter workflow-filter--limit">
        <span>Per sida</span>
        <select aria-label="Rader per sida" value={pageLimit} onChange={(event) => onPageLimitChange(Number(event.target.value))}>
          {[25, 50, 100].map((value) => <option value={value} key={value}>{value}</option>)}
          {![25, 50, 100].includes(pageLimit) ? <option value={pageLimit}>{pageLimit}</option> : null}
        </select>
      </label>
    </section>
  );
}
