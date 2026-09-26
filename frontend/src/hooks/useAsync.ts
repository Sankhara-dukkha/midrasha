// Generic hook: callers supply deps, which the linter cannot verify statically.
/* eslint-disable react-hooks/exhaustive-deps */
import { useEffect, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  error: Error | null
  loading: boolean
}

/** Run an async loader whenever `deps` change; ignores results from stale runs. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: true })

  useEffect(() => {
    let active = true
    setState((s) => ({ ...s, loading: true }))
    load()
      .then((data) => active && setState({ data, error: null, loading: false }))
      .catch((error: Error) => active && setState({ data: null, error, loading: false }))
    return () => {
      active = false
    }
  }, deps)

  return state
}
