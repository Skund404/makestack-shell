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
  registerKeyword('TIMER_', TimerWidget, 'core', {
    description: 'Countdown or duration timer',
    accepts: ['30min', '1h', '45s'],
    source: 'core',
  })
  registerKeyword('MEASUREMENT_', MeasurementWidget, 'core', {
    description: 'Numeric measurement with unit conversion',
    accepts: ['4mm', '2.5in', '150g'],
    source: 'core',
  })
  registerKeyword('MATERIAL_REF_', RefWidget, 'core', {
    description: 'Reference to a catalogue material',
    accepts: ['materials/leather/veg-tan-4oz'],
    source: 'core',
  })
  registerKeyword('TOOL_REF_', RefWidget, 'core', {
    description: 'Reference to a catalogue tool',
    accepts: ['tools/cutting/swivel-knife'],
    source: 'core',
  })
  registerKeyword('TECHNIQUE_REF_', RefWidget, 'core', {
    description: 'Reference to a catalogue technique',
    accepts: ['techniques/stitching/saddle-stitch'],
    source: 'core',
  })
  registerKeyword('IMAGE_', ImageWidget, 'core', {
    description: 'Inline image (URL or catalogue asset path)',
    accepts: ['https://…/photo.jpg', 'assets/images/step1.png'],
    source: 'core',
  })
  registerKeyword('LINK_', LinkWidget, 'core', {
    description: 'Hyperlink with optional label',
    accepts: ['https://example.com', 'https://example.com|Label'],
    source: 'core',
  })
  registerKeyword('NOTE_', NoteWidget, 'core', {
    description: 'Callout note (info / warning / tip)',
    accepts: ['Any free text or markdown'],
    source: 'core',
  })
  registerKeyword('CHECKLIST_', ChecklistWidget, 'core', {
    description: 'Interactive checklist of steps or items',
    accepts: ['["Step one","Step two"]'],
    source: 'core',
  })
}

export { KeywordValue } from './KeywordValue'
