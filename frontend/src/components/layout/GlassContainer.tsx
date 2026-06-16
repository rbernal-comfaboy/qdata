import { cn } from '../../lib/utils'

interface GlassContainerProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
}

export default function GlassContainer({ children, className, hover = true }: GlassContainerProps) {
  return (
    <div
      className={cn(
        'glass glass-card',
        hover && 'hover:shadow-xl hover:border-opacity-40',
        className,
      )}
    >
      {children}
    </div>
  )
}
