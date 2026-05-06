import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ChatView from '../views/ChatView.vue'
import RecordView from '../views/RecordView.vue'
import ProfileView from '../views/ProfileView.vue'
import LoginView from '../views/LoginView.vue'
import HealthProfile from '../views/HealthProfile.vue'
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/chat', name: 'chat', component: ChatView },
    { path: '/record', name: 'record', component: RecordView },
    { path: '/profile', name: 'profile', component: ProfileView },
    { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue') },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/healthprofile', name: 'healthprofile', component: HealthProfile },
  ],
})

export default router