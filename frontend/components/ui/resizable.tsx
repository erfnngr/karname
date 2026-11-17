import * as Panels from 'react-resizable-panels';
import { GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
export const ResizablePanelGroup = Panels.PanelGroup;
export const ResizablePanel = Panels.Panel;
export function ResizableHandle({className, ...props}: React.ComponentProps<typeof Panels.PanelResizeHandle>) {
  return <Panels.PanelResizeHandle className={cn('relative w-px bg-border flex items-center justify-center', className)} {...props}><GripVertical className="h-4 w-4 opacity-40" /></Panels.PanelResizeHandle>;
}
