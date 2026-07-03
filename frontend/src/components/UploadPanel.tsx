'use client'

import { useRef, useState } from 'react'
import { uploadDataset, type Dataset } from '@/lib/api'
import { Spinner } from './Spinner'

export function UploadPanel({
  dataset,
  onUploaded,
}: {
  dataset: Dataset | null
  onUploaded: (d: Dataset) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)

  async function handleFile(file: File | undefined) {
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please choose a .csv file. Excel and PDF support arrive in Phase 3.')
      return
    }
    setError(null)
    setUploading(true)
    try {
      const d = await uploadDataset(file)
      onUploaded(d)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed — please try again.')
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900">1 · Upload a dataset</h2>
        {dataset && (
          <span className="text-xs font-medium text-green-700">
            Loaded: {dataset.name}
          </span>
        )}
      </div>

      <div
        onDragOver={e => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => {
          e.preventDefault()
          setDragging(false)
          if (!uploading) void handleFile(e.dataTransfer.files?.[0])
        }}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50'
        }`}
      >
        <p className="mb-3 text-sm text-gray-500">
          Drag a CSV here, or choose a file to profile it.
        </p>
        <label className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-within:ring-2 focus-within:ring-blue-500">
          {dataset ? 'Choose a different CSV' : 'Choose CSV file'}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            disabled={uploading}
            onChange={e => void handleFile(e.target.files?.[0])}
          />
        </label>
      </div>

      {uploading && (
        <div className="mt-3">
          <Spinner label="Uploading and profiling…" />
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}
    </section>
  )
}
