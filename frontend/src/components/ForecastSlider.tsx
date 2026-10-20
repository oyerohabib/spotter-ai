import { CloudSun } from "lucide-react"

import { Card, CardContent } from "@/components/ui/card"
import { Slider } from "@/components/ui/slider"
import { cn } from "@/lib/utils"

interface ForecastSliderProps {
  hour: number
  onChange: (hour: number) => void
  disabled?: boolean
  className?: string
}

export function ForecastSlider({
  hour,
  onChange,
  disabled,
  className,
}: ForecastSliderProps) {
  return (
    <Card
      className={cn(
        "border-border/80 bg-card/95 shadow-none backdrop-blur",
        className,
      )}
    >
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CloudSun className="h-4 w-4 text-accent" />
            <p className="text-sm font-medium">Corridor weather forecast</p>
          </div>
          <p className="font-mono text-xs text-muted-foreground">
            +{hour}h <span className="text-foreground/70">/ 48h</span>
          </p>
        </div>
        <Slider
          min={0}
          max={48}
          step={1}
          value={[hour]}
          disabled={disabled}
          onValueChange={(value) => onChange(value[0] ?? 0)}
          aria-label="Forecast hour offset"
        />
        <div className="flex justify-between font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          <span>Now</span>
          <span>24h</span>
          <span>48h</span>
        </div>
      </CardContent>
    </Card>
  )
}
