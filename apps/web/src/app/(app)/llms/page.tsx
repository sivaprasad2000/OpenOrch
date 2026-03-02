'use client'

import { useEffect, useState } from 'react'
import { Plus, Trash2, Eye, EyeOff, Zap, Pencil } from 'lucide-react'
import { llmService } from '@/features/llms/services/llm.service'
import { userService } from '@/features/users/services/user.service'
import type { LLMProvider, LLMResponse } from '@/features/llms/types'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { EmptyState } from '@/components/ui/empty-state'
import { Modal } from '@/components/ui/modal'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { formatDateTime } from '@/lib/format'

const PROVIDERS: LLMProvider[] = [
  'openai',
  'anthropic',
  'google',
  'mistral',
  'cohere',
  'meta',
  'open_router',
]

const INPUT_CLS =
  'w-full px-3 py-2.5 bg-background border-2 border-foreground/20 text-foreground placeholder:text-foreground/30 font-mono text-sm focus:outline-none focus:border-accent transition-colors'
const PRI_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black font-mono text-sm font-semibold hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
const SEC_BTN =
  'inline-flex items-center gap-2 px-5 py-2.5 border-2 border-foreground/30 text-foreground font-mono text-sm hover:bg-foreground/10 transition-colors'

export default function LLMsPage() {
  const [llms, setLlms] = useState<LLMResponse[]>([])
  const [orgId, setOrgId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [addOpen, setAddOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [settingActiveId, setSettingActiveId] = useState<string | null>(null)

  // Add form state
  const [name, setName] = useState('')
  const [provider, setProvider] = useState<LLMProvider>('openai')
  const [apiKey, setApiKey] = useState('')
  const [modelName, setModelName] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  // Edit form state
  const [editLlm, setEditLlm] = useState<LLMResponse | null>(null)
  const [editName, setEditName] = useState('')
  const [editModelName, setEditModelName] = useState('')
  const [editApiKey, setEditApiKey] = useState('')
  const [editShowKey, setEditShowKey] = useState(false)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState('')

  async function loadData() {
    setLoading(true)
    try {
      const [user, llmList] = await Promise.all([
        userService.getMe(),
        llmService.list(),
      ])
      setOrgId(user.active_organization?.id ?? null)
      setLlms(llmList)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      await llmService.create({
        name: name.trim(),
        provider,
        api_key: apiKey,
        model_name: modelName.trim(),
      })
      setAddOpen(false)
      setName('')
      setProvider('openai')
      setApiKey('')
      setModelName('')
      setShowKey(false)
      loadData()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to add')
    } finally {
      setSaving(false)
    }
  }

  function openEdit(llm: LLMResponse) {
    setEditLlm(llm)
    setEditName(llm.name)
    setEditModelName(llm.model_name)
    setEditApiKey('')
    setEditShowKey(false)
    setEditError('')
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!editLlm) return
    setEditSaving(true)
    setEditError('')
    try {
      const patch: { name?: string; model_name?: string; api_key?: string } = {}
      if (editName.trim() !== editLlm.name) patch.name = editName.trim()
      if (editModelName.trim() !== editLlm.model_name)
        patch.model_name = editModelName.trim()
      if (editApiKey) patch.api_key = editApiKey
      await llmService.update(editLlm.id, patch)
      setEditLlm(null)
      loadData()
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Failed to update')
    } finally {
      setEditSaving(false)
    }
  }

  async function handleDelete() {
    if (!deleteId) return
    try {
      await llmService.delete(deleteId)
      setDeleteId(null)
      loadData()
    } catch {
      /* ignore */
    }
  }

  async function handleSetActive(llm: LLMResponse) {
    if (!orgId) return
    setSettingActiveId(llm.id)
    try {
      if (llm.is_active) {
        await llmService.unsetActive(orgId)
      } else {
        await llmService.setActive(orgId, llm.id)
      }
      loadData()
    } catch {
      /* ignore */
    } finally {
      setSettingActiveId(null)
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-mono text-3xl font-bold tracking-tight">
            LLM Providers
          </h1>
          <p className="mt-1 font-mono text-sm text-foreground/40">
            {llms.length} provider{llms.length !== 1 ? 's' : ''} configured
            {llms.some((l) => l.is_active) && (
              <span className="ml-2 text-accent">· 1 active</span>
            )}
          </p>
        </div>
        <button onClick={() => setAddOpen(true)} className={PRI_BTN}>
          <Plus size={14} strokeWidth={2} />
          Add LLM
        </button>
      </div>

      {llms.length === 0 ? (
        <EmptyState
          title="No LLM providers configured"
          description="Add an AI provider to enable test generation and execution."
          action={
            <button onClick={() => setAddOpen(true)} className={PRI_BTN}>
              <Plus size={14} strokeWidth={2} />
              Add LLM
            </button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {llms.map((llm) => {
            const isActive = llm.is_active
            const isSetting = settingActiveId === llm.id
            return (
              <div
                key={llm.id}
                className={`space-y-4 border p-5 transition-colors ${
                  isActive
                    ? 'border-accent/60 bg-accent/[0.02]'
                    : 'border-foreground/20'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-mono font-semibold">{llm.name}</p>
                      {isActive && <Badge variant="success">active</Badge>}
                    </div>
                    <Badge variant="neutral">{llm.provider}</Badge>
                  </div>
                  <div className="flex flex-shrink-0 items-center gap-3">
                    <button
                      onClick={() => openEdit(llm)}
                      className="inline-flex items-center gap-1 font-mono text-xs text-foreground/30 transition-colors hover:text-foreground"
                    >
                      <Pencil size={11} strokeWidth={1.5} />
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleteId(llm.id)}
                      className="inline-flex items-center gap-1 font-mono text-xs text-foreground/30 transition-colors hover:text-red-400"
                    >
                      <Trash2 size={11} strokeWidth={1.5} />
                      Delete
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <div>
                    <p className="mb-1 font-mono text-xs uppercase tracking-wider text-foreground/30">
                      Model
                    </p>
                    <p className="font-mono text-sm text-foreground/70">
                      {llm.model_name}
                    </p>
                  </div>
                  <div>
                    <p className="mb-1 font-mono text-xs uppercase tracking-wider text-foreground/30">
                      API Key
                    </p>
                    <p className="font-mono text-sm tracking-widest text-foreground/40">
                      ●●●●●●●●●●●●
                    </p>
                  </div>
                  <div>
                    <p className="mb-1 font-mono text-xs uppercase tracking-wider text-foreground/30">
                      Added
                    </p>
                    <p className="font-mono text-sm text-foreground/50">
                      {formatDateTime(llm.created_at)}
                    </p>
                  </div>
                </div>

                <div className="border-t border-border pt-1">
                  <button
                    onClick={() => handleSetActive(llm)}
                    disabled={isSetting || !orgId}
                    className={`inline-flex items-center gap-1.5 font-mono text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                      isActive
                        ? 'text-accent hover:text-foreground'
                        : 'text-foreground/40 hover:text-accent'
                    }`}
                  >
                    <Zap size={11} strokeWidth={1.5} />
                    {isSetting
                      ? 'Updating...'
                      : isActive
                        ? 'Unset active'
                        : 'Set as active'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Add Modal */}
      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add LLM Provider"
      >
        <form onSubmit={handleAdd} className="space-y-5">
          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              Name *
            </label>
            <input
              required
              placeholder="My OpenAI Key"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={INPUT_CLS}
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              Provider *
            </label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as LLMProvider)}
              className={INPUT_CLS}
            >
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>
                  {p === 'open_router'
                    ? 'OpenRouter'
                    : p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              Model Name *
            </label>
            <input
              required
              placeholder="gpt-4o"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              className={INPUT_CLS}
            />
          </div>

          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              API Key *
            </label>
            <div className="relative">
              <input
                required
                type={showKey ? 'text' : 'password'}
                placeholder="sk-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className={INPUT_CLS + ' pr-10'}
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground/30 transition-colors hover:text-foreground"
              >
                {showKey ? (
                  <EyeOff size={15} strokeWidth={1.5} />
                ) : (
                  <Eye size={15} strokeWidth={1.5} />
                )}
              </button>
            </div>
          </div>

          <div className="border border-foreground/20 bg-foreground/[0.02] p-3">
            <p className="font-mono text-xs text-foreground/40">
              Your API key is stored securely and never exposed in the UI.
            </p>
          </div>

          {saveError && (
            <div className="border-2 border-red-500 bg-red-500/10 p-3">
              <p className="font-mono text-sm text-red-500">{saveError}</p>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setAddOpen(false)}
              className={SEC_BTN}
            >
              Cancel
            </button>
            <button type="submit" disabled={saving} className={PRI_BTN}>
              {saving ? 'Adding...' : 'Add provider'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        open={!!editLlm}
        onClose={() => setEditLlm(null)}
        title="Edit LLM Provider"
      >
        <form onSubmit={handleEdit} className="space-y-5">
          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              Name *
            </label>
            <input
              required
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              className={INPUT_CLS}
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              Model Name *
            </label>
            <input
              required
              value={editModelName}
              onChange={(e) => setEditModelName(e.target.value)}
              className={INPUT_CLS}
            />
          </div>

          <div className="space-y-1.5">
            <label className="block font-mono text-sm text-foreground/70">
              New API Key
            </label>
            <div className="relative">
              <input
                type={editShowKey ? 'text' : 'password'}
                placeholder="Leave blank to keep existing key"
                value={editApiKey}
                onChange={(e) => setEditApiKey(e.target.value)}
                className={INPUT_CLS + ' pr-10'}
              />
              <button
                type="button"
                onClick={() => setEditShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground/30 transition-colors hover:text-foreground"
              >
                {editShowKey ? (
                  <EyeOff size={15} strokeWidth={1.5} />
                ) : (
                  <Eye size={15} strokeWidth={1.5} />
                )}
              </button>
            </div>
          </div>

          {editError && (
            <div className="border-2 border-red-500 bg-red-500/10 p-3">
              <p className="font-mono text-sm text-red-500">{editError}</p>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setEditLlm(null)}
              className={SEC_BTN}
            >
              Cancel
            </button>
            <button type="submit" disabled={editSaving} className={PRI_BTN}>
              {editSaving ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirm */}
      <ConfirmDialog
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleDelete}
        title="Remove LLM Provider"
        description="This provider and its API key will be permanently removed."
        confirmLabel="Remove"
        dangerous
      />
    </div>
  )
}
