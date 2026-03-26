import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import Login from '../views/Login.vue'
import OpportunityList from '../views/OpportunityList.vue'
import OpportunityDetail from '../views/OpportunityDetail.vue'
import OpportunityCreate from '../views/OpportunityCreate.vue'
import AccountList from '../views/AccountList.vue'
import ContactList from '../views/ContactList.vue'
import ContractList from '../views/ContractList.vue'
import ContractForm from '../views/ContractForm.vue'
import InvoiceList from '../views/InvoiceList.vue'
import PaymentList from '../views/PaymentList.vue'
import ActivityList from '../views/ActivityList.vue'
import TaskList from '../views/TaskList.vue'

const routes = [
  { path: '/login', name: 'login', component: Login },
  { path: '/', redirect: '/opportunities' },
  { path: '/opportunities', name: 'opportunities', component: OpportunityList },
  { path: '/opportunities/new', name: 'opportunity-create', component: OpportunityCreate },
  { path: '/opportunities/:id', name: 'opportunity-detail', component: OpportunityDetail, props: true },
  { path: '/accounts', name: 'accounts', component: AccountList },
  { path: '/contacts', name: 'contacts', component: ContactList },
  { path: '/contracts', name: 'contracts', component: ContractList },
  { path: '/contracts/new', name: 'contract-create', component: ContractForm },
  { path: '/contracts/:id', name: 'contract-detail', component: ContractForm, props: true },
  { path: '/invoices', name: 'invoices', component: InvoiceList },
  { path: '/payments', name: 'payments', component: PaymentList },
  { path: '/activities', name: 'activities', component: ActivityList },
  { path: '/tasks', name: 'tasks', component: TaskList }
]

const router = createRouter({
  history: createWebHistory('/app/'),
  routes
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name !== 'login' && !auth.accessToken) {
    return { name: 'login' }
  }
  if (to.name === 'login' && auth.accessToken) {
    return { name: 'opportunities' }
  }
})

export default router
