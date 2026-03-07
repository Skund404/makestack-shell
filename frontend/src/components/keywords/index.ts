/**
 * Core widget registration. Call registerCoreWidgets() during app init.
 */
import { registerKeyword } from '@/modules/keyword-resolver'
import { ChecklistWidget } from './ChecklistWidget'
import { ImageWidget } from './ImageWidget'
import { LinkWidget } from './LinkWidget'
import { MeasurementWidget } from './MeasurementWidget'
import { NoteWidget } from './NoteWidget'
import { RefWidget } from './RefWidget'
import { TimerWidget } from './TimerWidget'

export function registerCoreWidgets(): void {
  registerKeyword('TIMER_', TimerWidget)
  registerKeyword('MEASUREMENT_', MeasurementWidget)
  registerKeyword('MATERIAL_REF_', RefWidget)
  registerKeyword('TOOL_REF_', RefWidget)
  registerKeyword('TECHNIQUE_REF_', RefWidget)
  registerKeyword('IMAGE_', ImageWidget)
  registerKeyword('LINK_', LinkWidget)
  registerKeyword('NOTE_', NoteWidget)
  registerKeyword('CHECKLIST_', ChecklistWidget)
}

export { KeywordValue } from './KeywordValue'
