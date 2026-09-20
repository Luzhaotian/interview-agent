import { createRouter, createWebHistory } from 'vue-router'

/** Shell renders chat directly; router kept for history / future deep links. */
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [{ path: '/:pathMatch(.*)*', name: 'home', component: { template: '<div />' } }],
})

export default router
