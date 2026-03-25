<template>
  <div v-if="!auth.accessToken" class="main">
    <router-view />
  </div>
  <div v-else class="layout">
    <aside class="sidebar">
      <div class="brand">徐师傅 CRM</div>
      <nav class="nav">
        <div class="nav-group">销售管理</div>
        <router-link to="/opportunities"><span class="nav-icon">◎</span>商机</router-link>
        <router-link to="/activities"><span class="nav-icon">✎</span>商机跟进</router-link>
        <div class="nav-group">客户资料</div>
        <router-link to="/accounts"><span class="nav-icon">◼</span>客户</router-link>
        <router-link to="/contacts"><span class="nav-icon">●</span>联系人</router-link>
        <div class="nav-group">合同与回款</div>
        <router-link to="/contracts"><span class="nav-icon">▣</span>合同</router-link>
        <router-link to="/invoices"><span class="nav-icon">▤</span>开票申请</router-link>
        <router-link to="/payments"><span class="nav-icon">◆</span>回款</router-link>
        <div class="nav-group">任务协同</div>
        <router-link to="/tasks"><span class="nav-icon">◐</span>任务</router-link>
      </nav>
      <button class="button secondary" @click="auth.logout()">退出</button>
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()

onMounted(async () => {
  if (auth.accessToken && !auth.user) {
    try {
      await auth.fetchMe()
    } catch (err) {
      auth.logout()
    }
  }
})
</script>
