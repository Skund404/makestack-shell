/**
 * Shared icon resolver — maps icon name strings to Lucide components.
 *
 * Used by both the shell Sidebar and ModuleAppSidebar so icon resolution
 * is consistent across the entire application.
 */
import {
  Archive,
  Blocks,
  BookOpen,
  Box,
  Calendar,
  ChefHat,
  ClipboardList,
  Cog,
  Cpu,
  Database,
  FlaskConical,
  Folder,
  GitFork,
  Globe,
  Hammer,
  Home,
  Layers,
  LayoutGrid,
  Package,
  Puzzle,
  ScrollText,
  Search,
  ShieldCheck,
  ShoppingCart,
  Snowflake,
  Star,
  Tag,
  Terminal,
  Thermometer,
  UtensilsCrossed,
  Wrench,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import React from 'react'

export const ICON_MAP: Record<string, LucideIcon> = {
  archive:         Archive,
  blocks:          Blocks,
  book:            BookOpen,
  bookopen:        BookOpen,
  box:             Box,
  calendar:        Calendar,
  chefhat:         ChefHat,
  clipboardlist:   ClipboardList,
  cog:             Cog,
  cpu:             Cpu,
  database:        Database,
  flaskconical:    FlaskConical,
  folder:          Folder,
  'git-fork':      GitFork,
  gitfork:         GitFork,
  globe:           Globe,
  hammer:          Hammer,
  home:            Home,
  layers:          Layers,
  'layout-grid':   LayoutGrid,
  layoutgrid:      LayoutGrid,
  package:         Package,
  puzzle:          Puzzle,
  scrolltext:      ScrollText,
  search:          Search,
  shield:          ShieldCheck,
  shieldcheck:     ShieldCheck,
  shoppingcart:    ShoppingCart,
  snowflake:       Snowflake,
  star:            Star,
  tag:             Tag,
  terminal:        Terminal,
  thermometer:     Thermometer,
  utensilscrossed: UtensilsCrossed,
  wrench:          Wrench,
  zap:             Zap,
}

/** Resolve a Lucide icon name string → LucideIcon component. Falls back to Box. */
export function getIcon(name: string): LucideIcon {
  return ICON_MAP[name?.toLowerCase() ?? ''] ?? Box
}

/** Resolve a Lucide icon name string → rendered icon node. Falls back to Box. */
export function resolveIcon(name: string, size = 14): React.ReactNode {
  const Icon = getIcon(name)
  return React.createElement(Icon, { size })
}
