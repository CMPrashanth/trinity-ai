import { Dispatch, SetStateAction, useEffect, useRef, useState } from "react";

type InitialValue<T> = T | (() => T);

type PersistentStateReturn<T> = [T, Dispatch<SetStateAction<T>>];

function resolveInitialValue<T>(value: InitialValue<T>): T {
  return typeof value === "function" ? (value as () => T)() : value;
}

export function usePersistentState<T>(key: string, initialValue: InitialValue<T>): PersistentStateReturn<T> {
  const hasMountedRef = useRef(false);

  const [state, setState] = useState<T>(() => {
    if (typeof window === "undefined") {
      return resolveInitialValue(initialValue);
    }

    try {
      const stored = window.localStorage.getItem(key);
      if (stored !== null) {
        return JSON.parse(stored) as T;
      }
    } catch (error) {
      console.warn(`Unable to read persistent state for key "${key}":`, error);
    }

    return resolveInitialValue(initialValue);
  });

  useEffect(() => {
    if (!hasMountedRef.current) {
      hasMountedRef.current = true;
      return;
    }

    try {
      window.localStorage.setItem(key, JSON.stringify(state));
    } catch (error) {
      console.warn(`Unable to persist state for key "${key}":`, error);
    }
  }, [key, state]);

  return [state, setState];
}
