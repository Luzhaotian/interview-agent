import {
  defineConfig,
  presetIcons,
  presetWind3,
  transformerDirectives,
  transformerVariantGroup,
} from 'unocss'

export default defineConfig({
  presets: [
    presetWind3(),
    presetIcons({
      scale: 1.1,
      extraProperties: {
        display: 'inline-block',
        'vertical-align': 'middle',
      },
    }),
  ],
  transformers: [transformerDirectives(), transformerVariantGroup()],
  // 避免模板里的 <h1>/<h2>/<h3> 被抽成 height 工具类
  blocklist: [/^h[1-6]$/],
  theme: {
    colors: {
      ink: '#12202e',
      muted: '#5b6b7c',
      // 用实色；透明度在工具类里写 /10、/90，避免 rgba 主题色被拆坏
      line: '#12202e',
      panel: '#ffffff',
      'panel-strong': '#ffffff',
      accent: '#0b7a6a',
      'accent-soft': '#d8f3ec',
      warn: '#b42318',
      rail: '#12202e',
      soft: '#f7faf8',
    },
    fontFamily: {
      display: '"Fraunces", "Songti SC", serif',
      body: '"Manrope", "PingFang SC", "Noto Sans SC", sans-serif',
      mono: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    },
    boxShadow: {
      panel: '0 18px 50px rgba(18, 32, 46, 0.08)',
      bubble: '0 6px 18px rgba(18, 32, 46, 0.06)',
      drawer: '-18px 0 50px rgba(18, 32, 46, 0.16)',
      jump: '0 8px 24px rgba(18, 32, 46, 0.12)',
      preview: '0 10px 24px rgba(18, 32, 46, 0.18)',
    },
    borderRadius: {
      panel: '18px',
    },
  },
  // bg-[linear-gradient(...)] 会被生成成无效的 background-color，这里用真正的 background
  rules: [
    [
      'bg-rail',
      {
        background:
          'linear-gradient(180deg, rgba(18, 32, 46, 0.98), rgba(14, 58, 56, 0.92)), #12202e',
      },
    ],
    [
      'bg-bubble-user',
      {
        background: 'linear-gradient(180deg, #e7f7f2, #dff3ec)',
      },
    ],
  ],
  shortcuts: {
    'page-shell': 'h-screen overflow-auto px-8 py-7 max-md:h-auto max-md:p-4',
    'page-embedded': 'flex h-full min-h-0 flex-col px-[18px] py-4 pb-5',
    eyebrow: 'm-0 text-accent tracking-[0.14em] uppercase text-xs font-bold',
    'kb-row':
      'grid w-full gap-0.5 border-0 border-b border-line/8 bg-transparent px-3 py-2.5 text-left text-inherit hover:bg-[rgba(11,122,106,0.05)] data-[active=true]:bg-accent-soft',
    'diff-pill':
      'inline-block flex-none rounded-md px-1.5 py-px text-[11px] font-bold leading-snug tracking-wide',
    'display-title': 'font-display tracking-tight',
    'panel-card':
      'border border-line/10 rounded-panel bg-white/92 backdrop-blur-sm shadow-panel',
    'bubble-card':
      'border border-line/10 rounded-panel bg-white/92 backdrop-blur-sm shadow-bubble',
    'btn-base': 'rounded-xl border border-line/10 bg-panel-strong px-3 py-2',
    'btn-ghost': 'btn-base',
    'btn-accent': 'btn-base border-accent bg-accent text-white font-semibold',
    'btn-tool':
      'inline-flex items-center gap-1.5 rounded-lg border border-line/10 bg-panel-strong px-3 py-1.5 text-[13px]',
    'filter-chip':
      'flex-none whitespace-nowrap border border-line/10 rounded-xl bg-panel-strong px-3 py-2 data-[on=true]:bg-accent data-[on=true]:border-accent data-[on=true]:text-white',
    'tag-chip':
      'flex-none whitespace-nowrap border border-line/10 rounded-full bg-panel-strong px-2 py-0.5 text-xs leading-snug text-muted data-[on=true]:bg-accent-soft data-[on=true]:border-transparent data-[on=true]:text-accent data-[on=true]:font-bold',
    'pill-em':
      'inline-block mr-2 px-2 py-px rounded-full bg-accent-soft text-accent not-italic text-xs font-bold',
    'composer-box': 'grid gap-2 rounded-panel border border-line/10 bg-white/92 p-3 shadow-panel',
    'profile-cell': 'rounded-xl bg-white/90 px-3 py-2.5',
  },
  safelist: [
    'drawer-fade-enter-active',
    'drawer-fade-leave-active',
    'drawer-fade-enter-from',
    'drawer-fade-leave-to',
    'drawer-slide-enter-active',
    'drawer-slide-leave-active',
    'drawer-slide-enter-from',
    'drawer-slide-leave-to',
  ],
})
