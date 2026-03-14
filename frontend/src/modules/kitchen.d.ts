/**
 * Type declarations for the @kitchen-frontend module alias.
 *
 * The alias is resolved by Vite at build/dev time (see vite.config.ts).
 * This file tells TypeScript the module's public surface so registry.ts
 * can import from it without errors. The kitchen module's own files are
 * not type-checked here — they are processed by Vite's bundler directly.
 *
 * Generated once; updated by scripts/generate_module_registry.py on
 * install/uninstall of the kitchen module.
 */
declare module '@kitchen-frontend' {
  export function registerKitchenModule(): void
}
