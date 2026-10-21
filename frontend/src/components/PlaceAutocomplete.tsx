import { Loader2, MapPin } from "lucide-react"
import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
} from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { suggestPlaces, ApiError } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { PlaceSuggestion, SelectedPlace } from "@/types/routing"

interface PlaceAutocompleteProps {
  id?: string
  label: string
  value: string
  selected: SelectedPlace | null
  error?: string | null
  helperText?: string | null
  disabled?: boolean
  placeholder?: string
  onQueryChange: (value: string) => void
  onSelect: (place: SelectedPlace) => void
  onClearSelection: () => void
}

export function PlaceAutocomplete({
  id,
  label,
  value,
  selected,
  error,
  helperText,
  disabled,
  placeholder = "City or address",
  onQueryChange,
  onSelect,
  onClearSelection,
}: PlaceAutocompleteProps) {
  const listId = useId()
  const errorId = `${listId}-error`
  const helperId = `${listId}-helper`
  const statusId = `${listId}-status`
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<PlaceSuggestion[]>([])
  const [activeIndex, setActiveIndex] = useState(-1)
  const [suggestError, setSuggestError] = useState<string | null>(null)
  const [statusText, setStatusText] = useState("")

  useEffect(() => {
    const q = value.trim()
    if (selected && selected.name === value) {
      setResults([])
      setOpen(false)
      setLoading(false)
      setStatusText("")
      return
    }
    if (q.length < 2) {
      setResults([])
      setLoading(false)
      setSuggestError(null)
      setStatusText("")
      return
    }

    let cancelled = false
    setLoading(true)
    setSuggestError(null)
    const timer = window.setTimeout(async () => {
      try {
        const next = await suggestPlaces(q)
        if (cancelled) return
        setResults(next)
        setOpen(true)
        setActiveIndex(-1)
        setStatusText(
          next.length === 0
            ? "No matching places"
            : `${next.length} suggestion${next.length === 1 ? "" : "s"}`,
        )
      } catch (err) {
        if (cancelled) return
        setResults([])
        setSuggestError(
          err instanceof ApiError
            ? err.message
            : "Couldn’t search places right now.",
        )
        setOpen(true)
        setStatusText("Place search failed")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 300)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [value, selected])

  useEffect(() => {
    function onDocClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onDocClick)
    return () => document.removeEventListener("mousedown", onDocClick)
  }, [])

  function choose(place: PlaceSuggestion) {
    onSelect({ name: place.name, lon: place.lon, lat: place.lat })
    onQueryChange(place.name)
    setOpen(false)
    setResults([])
    setSuggestError(null)
    setStatusText(`Selected ${place.name}`)
  }

  function handleChange(next: string) {
    onQueryChange(next)
    if (selected && next !== selected.name) {
      onClearSelection()
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open || (!results.length && !suggestError)) return
    if (event.key === "ArrowDown") {
      event.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, results.length - 1))
    } else if (event.key === "ArrowUp") {
      event.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (event.key === "Enter" && activeIndex >= 0 && results[activeIndex]) {
      event.preventDefault()
      choose(results[activeIndex])
    } else if (event.key === "Escape") {
      setOpen(false)
    }
  }

  const showNoMatches =
    open &&
    !loading &&
    !suggestError &&
    value.trim().length >= 2 &&
    results.length === 0 &&
    !selected

  const describedBy = [
    error ? errorId : null,
    !error && helperText ? helperId : null,
    statusText ? statusId : null,
  ]
    .filter(Boolean)
    .join(" ")

  const activeOptionId =
    activeIndex >= 0 ? `${listId}-opt-${activeIndex}` : undefined

  return (
    <div ref={containerRef} className="relative space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        <Input
          id={id}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (results.length || suggestError || showNoMatches) setOpen(true)
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-activedescendant={activeOptionId}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy || undefined}
          className={cn(error && "border-destructive focus-visible:ring-destructive")}
        />
        {loading ? (
          <Loader2
            aria-hidden
            className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground"
          />
        ) : selected ? (
          <MapPin
            aria-hidden
            className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-primary"
          />
        ) : null}
      </div>

      <div id={statusId} className="sr-only" aria-live="polite" aria-atomic="true">
        {loading ? "Searching places" : statusText}
      </div>

      {open && (results.length > 0 || suggestError || showNoMatches) ? (
        <ul
          id={listId}
          role="listbox"
          className="absolute z-30 mt-1 max-h-56 w-full overflow-auto rounded-md border border-border bg-card py-1 shadow-md"
        >
          {suggestError ? (
            <li className="px-3 py-2 text-sm text-destructive" role="presentation">
              {suggestError}
            </li>
          ) : showNoMatches ? (
            <li className="px-3 py-2 text-sm text-muted-foreground" role="presentation">
              No matches. Try a city and state, e.g. “Chicago, IL”.
            </li>
          ) : (
            results.map((place, index) => (
              <li key={place.id} role="presentation">
                <button
                  type="button"
                  id={`${listId}-opt-${index}`}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={cn(
                    "flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    index === activeIndex && "bg-muted",
                  )}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => choose(place)}
                >
                  <MapPin
                    aria-hidden
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  />
                  <span>{place.name}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}

      {error ? (
        <p id={errorId} className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : helperText ? (
        <p id={helperId} className="text-xs text-muted-foreground">
          {helperText}
        </p>
      ) : null}
    </div>
  )
}
