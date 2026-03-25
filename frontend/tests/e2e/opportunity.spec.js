import { expect, test } from '@playwright/test'

const ADMIN_USERNAME = process.env.E2E_USERNAME || 'admin'
const ADMIN_PASSWORD = process.env.E2E_PASSWORD || '123456'

const apiLogin = async (request) => {
  const response = await request.post('/api/auth/jwt/', {
    data: { username: ADMIN_USERNAME, password: ADMIN_PASSWORD }
  })
  if (!response.ok()) {
    throw new Error(`Login failed with status ${response.status()}`)
  }
  const data = await response.json()
  return { access: data.access, refresh: data.refresh }
}

const getAdminUserId = async (request, accessToken) => {
  const response = await request.get('/api/users/', {
    headers: { Authorization: `Bearer ${accessToken}` }
  })
  if (!response.ok()) {
    throw new Error(`Fetch users failed with status ${response.status()}`)
  }
  const data = await response.json()
  const users = Array.isArray(data) ? data : (data.results || [])
  const admin = users.find((item) => item.username === ADMIN_USERNAME)
  if (!admin) {
    throw new Error('Admin user not found')
  }
  return admin.id
}

const ensureRegion = async (request, accessToken) => {
  const listResp = await request.get('/api/regions/', {
    headers: { Authorization: `Bearer ${accessToken}` }
  })
  if (!listResp.ok()) {
    throw new Error(`Fetch regions failed with status ${listResp.status()}`)
  }
  const data = await listResp.json()
  const regions = Array.isArray(data) ? data : (data.results || [])
  if (regions.length > 0) {
    return { id: regions[0].id, created: false }
  }

  const code = `e2e-${Date.now()}`
  const createResp = await request.post('/api/regions/', {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { name: 'E2E Region', code }
  })
  if (!createResp.ok()) {
    throw new Error(`Create region failed with status ${createResp.status()}`)
  }
  const created = await createResp.json()
  return { id: created.id, created: true }
}

const createOpportunity = async (request, accessToken, payload) => {
  const response = await request.post('/api/opportunities/', {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: payload
  })
  if (!response.ok()) {
    throw new Error(`Create opportunity failed with status ${response.status()}`)
  }
  return response.json()
}

const loginUI = async (page) => {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(ADMIN_USERNAME)
  await page.getByLabel('密码').fill(ADMIN_PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/opportunities$/)
}

let accessToken = ''
let createdOppIds = []
let createdRegionId = null
let createdRegionOwned = false
let opportunityNames = []

test.beforeAll(async ({ request }) => {
  const tokens = await apiLogin(request)
  accessToken = tokens.access

  const { id, created } = await ensureRegion(request, accessToken)
  createdRegionId = id
  createdRegionOwned = created

  const adminId = await getAdminUserId(request, accessToken)
  const timestamp = Date.now()
  opportunityNames = [`E2E Opportunity ${timestamp}`, `E2E Search Target ${timestamp}`]

  const opp1 = await createOpportunity(request, accessToken, {
    opportunity_name: opportunityNames[0],
    region: createdRegionId,
    owner: adminId,
    stage: 'lead'
  })
  const opp2 = await createOpportunity(request, accessToken, {
    opportunity_name: opportunityNames[1],
    region: createdRegionId,
    owner: adminId,
    stage: 'won'
  })
  createdOppIds = [opp1.id, opp2.id]
})

test.afterAll(async ({ request }) => {
  if (!accessToken) return
  for (const id of createdOppIds) {
    await request.delete(`/api/opportunities/${id}/`, {
      headers: { Authorization: `Bearer ${accessToken}` }
    })
  }
  if (createdRegionOwned && createdRegionId) {
    await request.delete(`/api/regions/${createdRegionId}/`, {
      headers: { Authorization: `Bearer ${accessToken}` }
    })
  }
})

test('login redirects to opportunities list', async ({ page }) => {
  await loginUI(page)
  await expect(page.getByRole('heading', { name: '商机' })).toBeVisible()
})

test('search filters and opens opportunity detail', async ({ page }) => {
  await loginUI(page)

  const searchInput = page.getByPlaceholder('搜索商机名称')
  await searchInput.fill(opportunityNames[1])
  await page.getByRole('button', { name: '搜索' }).click()

  const listRow = page.locator('.list-row', { hasText: opportunityNames[1] })
  await expect(listRow).toBeVisible()
  await expect(page.locator('.list-row', { hasText: opportunityNames[0] })).toHaveCount(0)

  await listRow.getByRole('link', { name: '详情' }).click()
  await expect(page).toHaveURL(/\/opportunities\//)
  await expect(page.getByText(opportunityNames[1])).toBeVisible()
})
