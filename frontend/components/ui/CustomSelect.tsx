"use client";

import * as React from "react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
  disabled?: boolean;
  placeholder?: string;
  accent?: "indigo" | "emerald" | "rose" | "cyan" | "violet" | "orange";
  className?: string;
}

const accentStyles = {
  indigo: {
    ring: "focus:ring-indigo-500/30",
    border: "focus:border-indigo-500",
    hover: "hover:border-indigo-300 dark:hover:border-indigo-700",
    bg: "bg-indigo-50 dark:bg-indigo-900/20",
    text: "text-indigo-600 dark:text-indigo-400",
  },
  emerald: {
    ring: "focus:ring-emerald-500/30",
    border: "focus:border-emerald-500",
    hover: "hover:border-emerald-300 dark:hover:border-emerald-700",
    bg: "bg-emerald-50 dark:bg-emerald-900/20",
    text: "text-emerald-600 dark:text-emerald-400",
  },
  rose: {
    ring: "focus:ring-rose-500/30",
    border: "focus:border-rose-500",
    hover: "hover:border-rose-300 dark:hover:border-rose-700",
    bg: "bg-rose-50 dark:bg-rose-900/20",
    text: "text-rose-600 dark:text-rose-400",
  },
  cyan: {
    ring: "focus:ring-cyan-500/30",
    border: "focus:border-cyan-500",
    hover: "hover:border-cyan-300 dark:hover:border-cyan-700",
    bg: "bg-cyan-50 dark:bg-cyan-900/20",
    text: "text-cyan-600 dark:text-cyan-400",
  },
  violet: {
    ring: "focus:ring-violet-500/30",
    border: "focus:border-violet-500",
    hover: "hover:border-violet-300 dark:hover:border-violet-700",
    bg: "bg-violet-50 dark:bg-violet-900/20",
    text: "text-violet-600 dark:text-violet-400",
  },
  orange: {
    ring: "focus:ring-orange-500/30",
    border: "focus:border-orange-500",
    hover: "hover:border-orange-300 dark:hover:border-orange-700",
    bg: "bg-orange-50 dark:bg-orange-900/20",
    text: "text-orange-600 dark:text-orange-400",
  },
};

export function CustomSelect({
  value,
  onChange,
  options,
  disabled = false,
  placeholder = "Select an option",
  accent = "indigo",
  className,
}: CustomSelectProps) {
  const [isOpen, setIsOpen] = React.useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const listRef = React.useRef<HTMLUListElement>(null);
  const [focusedIndex, setFocusedIndex] = React.useState(-1);

  const colors = accentStyles[accent];

  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setFocusedIndex(-1);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Scroll focused item into view
  React.useEffect(() => {
    if (isOpen && focusedIndex >= 0 && listRef.current) {
      const item = listRef.current.children[focusedIndex] as HTMLElement;
      item?.scrollIntoView({ block: "nearest" });
    }
  }, [focusedIndex, isOpen]);

  const selectedOption = options.find((opt) => opt.value === value);

  const handleSelect = (optionValue: string) => {
    if (disabled) return;
    onChange(optionValue);
    setIsOpen(false);
    setFocusedIndex(-1);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;

    switch (e.key) {
      case "Enter":
      case " ":
        e.preventDefault();
        if (isOpen) {
          if (focusedIndex >= 0 && focusedIndex < options.length) {
            handleSelect(options[focusedIndex].value);
          } else {
            setIsOpen(false);
          }
        } else {
          setIsOpen(true);
          const idx = options.findIndex((opt) => opt.value === value);
          setFocusedIndex(idx >= 0 ? idx : 0);
        }
        break;
      case "Escape":
        e.preventDefault();
        setIsOpen(false);
        setFocusedIndex(-1);
        break;
      case "ArrowDown":
        e.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setFocusedIndex(0);
        } else {
          setFocusedIndex((prev) => (prev < options.length - 1 ? prev + 1 : prev));
        }
        break;
      case "ArrowUp":
        e.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
          setFocusedIndex(options.length - 1);
        } else {
          setFocusedIndex((prev) => (prev > 0 ? prev - 1 : prev));
        }
        break;
      case "Tab":
        if (isOpen) setIsOpen(false);
        break;
    }
  };

  return (
    <div ref={containerRef} className={cn("relative w-full", className)} onKeyDown={handleKeyDown}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (!disabled) {
            setIsOpen(!isOpen);
            if (!isOpen) {
              const idx = options.findIndex((opt) => opt.value === value);
              setFocusedIndex(idx >= 0 ? idx : 0);
            }
          }
        }}
        className={cn(
          "relative w-full appearance-none px-3 py-2 pr-10 text-left text-sm font-medium",
          "rounded-lg border-2 border-gray-200 dark:border-gray-600",
          "bg-white dark:bg-gray-900",
          "text-gray-900 dark:text-gray-100",
          "transition-all cursor-pointer hover:shadow-sm",
          "focus:outline-none focus:ring-2",
          colors.ring,
          colors.border,
          colors.hover,
          disabled && "opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800"
        )}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <span className="block truncate">
          {selectedOption ? selectedOption.label : placeholder}
        </span>
        <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400">
          <ChevronDown
            className={cn("h-4 w-4 transition-transform duration-200", isOpen && "rotate-180")}
            aria-hidden="true"
          />
        </span>
      </button>

      <div
        className={cn(
          "absolute z-50 mt-1 w-full overflow-hidden rounded-lg bg-white dark:bg-gray-800 shadow-lg border border-gray-200 dark:border-gray-700",
          "transition-all duration-200 ease-out origin-top",
          isOpen
            ? "opacity-100 scale-100 visible"
            : "opacity-0 scale-95 invisible pointer-events-none"
        )}
      >
        <ul
          ref={listRef}
          className="max-h-60 overflow-auto py-1 text-sm focus:outline-none"
          role="listbox"
        >
          {options.map((option, index) => {
            const isSelected = option.value === value;
            const isFocused = index === focusedIndex;

            return (
              <li
                key={option.value}
                role="option"
                aria-selected={isSelected}
                onClick={() => handleSelect(option.value)}
                onMouseEnter={() => setFocusedIndex(index)}
                className={cn(
                  "relative cursor-pointer select-none py-2.5 pl-3 pr-9",
                  "text-gray-900 dark:text-gray-100",
                  "transition-colors duration-100",
                  (isSelected || isFocused) && colors.bg
                )}
              >
                <span className={cn("block truncate", isSelected ? "font-semibold" : "font-normal")}>
                  {option.label}
                </span>
                {isSelected && (
                  <span className={cn("absolute inset-y-0 right-0 flex items-center pr-3", colors.text)}>
                    <Check className="h-4 w-4" aria-hidden="true" />
                  </span>
                )}
              </li>
            );
          })}
          {options.length === 0 && (
            <li className="relative cursor-default select-none py-2.5 pl-3 pr-9 text-gray-500">
              No options available
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
