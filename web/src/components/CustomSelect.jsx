import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, Check, Search } from 'lucide-react';

export default function CustomSelect({
  value,
  onChange,
  options = [],
  placeholder = 'Select an option',
  className = '',
  menuClassName = '',
  size = 'md', // 'sm' | 'md'
  icon: TriggerIcon = null,
  showSearch = null, // auto if options > 8 unless explicitly true/false
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const containerRef = useRef(null);
  const searchInputRef = useRef(null);

  // Normalize options to { value, label, badge, icon, sublabel }
  const normalizedOptions = useMemo(() => {
    return options.map((opt) => {
      if (typeof opt === 'string' || typeof opt === 'number') {
        return { value: opt, label: String(opt) };
      }
      return opt;
    });
  }, [options]);

  const selectedOption = normalizedOptions.find((o) => o.value === value) || {
    value,
    label: value ?? placeholder,
  };

  const shouldShowSearch = showSearch !== null ? showSearch : normalizedOptions.length > 8;

  // Filter options based on search query
  const filteredOptions = useMemo(() => {
    if (!searchTerm.trim()) return normalizedOptions;
    const lower = searchTerm.toLowerCase();
    return normalizedOptions.filter(
      (opt) =>
        opt.label.toLowerCase().includes(lower) ||
        (opt.badge && String(opt.badge).toLowerCase().includes(lower))
    );
  }, [normalizedOptions, searchTerm]);

  // Focus search input when opening
  useEffect(() => {
    if (isOpen) {
      setSearchTerm('');
      if (shouldShowSearch) {
        setTimeout(() => searchInputRef.current?.focus(), 50);
      }
    }
  }, [isOpen, shouldShowSearch]);

  // Close when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        setIsOpen(false);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        const currentIdx = filteredOptions.findIndex((o) => o.value === value);
        const nextIdx = (currentIdx + 1) % filteredOptions.length;
        if (filteredOptions[nextIdx]) {
          onChange(filteredOptions[nextIdx].value);
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const currentIdx = filteredOptions.findIndex((o) => o.value === value);
        const prevIdx = (currentIdx - 1 + filteredOptions.length) % filteredOptions.length;
        if (filteredOptions[prevIdx]) {
          onChange(filteredOptions[prevIdx].value);
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        setIsOpen(false);
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, value, filteredOptions, onChange]);

  const pyClass = size === 'sm' ? 'py-1 px-2.5 text-xs' : 'py-1.5 px-3 text-xs';

  return (
    <div className={`relative select-none ${className}`} ref={containerRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className={`w-full rounded-xl border bg-white/85 hover:bg-white text-slate-800 transition-all flex items-center justify-between gap-2 shadow-2xs cursor-pointer ${
          isOpen
            ? 'border-sky-500/80 ring-2 ring-sky-500/15 bg-white'
            : 'border-slate-200/90 hover:border-slate-300'
        } ${pyClass}`}
      >
        <div className="flex items-center gap-2 min-w-0 truncate">
          {TriggerIcon && <TriggerIcon className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
          {selectedOption.icon && (
            <span className="shrink-0">{selectedOption.icon}</span>
          )}
          <span className="font-medium truncate tracking-tight text-slate-800">
            {selectedOption.label}
          </span>
          {selectedOption.badge && (
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-100 text-slate-600 font-normal shrink-0 border border-slate-200/60">
              {selectedOption.badge}
            </span>
          )}
        </div>

        <ChevronDown
          className={`w-3.5 h-3.5 text-slate-400 shrink-0 transition-transform duration-200 ${
            isOpen ? 'rotate-180 text-sky-600' : ''
          }`}
        />
      </button>

      {/* Floating Glass Dropdown Popup */}
      {isOpen && (
        <div
          role="listbox"
          className={`absolute left-0 right-0 z-50 mt-1.5 min-w-[220px] max-h-64 overflow-hidden flex flex-col rounded-xl border border-slate-200/90 bg-white/95 backdrop-blur-2xl shadow-[0_16px_36px_-6px_rgba(15,23,42,0.16),0_4px_12px_rgba(15,23,42,0.06)] animate-fade-in ${menuClassName}`}
        >
          {/* Optional inline search for long lists */}
          {shouldShowSearch && (
            <div className="p-1.5 border-b border-slate-100 bg-slate-50/70">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  ref={searchInputRef}
                  type="text"
                  placeholder="Search..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  className="w-full pl-8 pr-2.5 py-1 text-xs rounded-lg bg-white border border-slate-200/80 focus:outline-none focus:border-sky-400 focus:ring-1 focus:ring-sky-400/20 text-slate-800 placeholder-slate-400"
                />
              </div>
            </div>
          )}

          {/* Options List */}
          <div
            className="overflow-y-auto p-1.5 space-y-0.5 flex-1"
            style={{
              scrollbarWidth: 'thin',
              scrollbarColor: '#cbd5e1 transparent',
            }}
          >
            {filteredOptions.length === 0 ? (
              <div className="py-3 text-center text-xs text-slate-400">
                No matching options
              </div>
            ) : (
              filteredOptions.map((opt, idx) => {
                const isSelected = opt.value === value;
                return (
                  <button
                    key={`${opt.value}-${idx}`}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => {
                      onChange(opt.value);
                      setIsOpen(false);
                    }}
                    className={`w-full rounded-lg px-2.5 py-1.5 text-xs text-left transition-all flex items-center justify-between gap-2 cursor-pointer ${
                      isSelected
                        ? 'bg-sky-50 text-sky-800 font-semibold border border-sky-200/60 shadow-2xs'
                        : 'text-slate-700 hover:bg-slate-100/80 hover:text-slate-900 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center gap-2 min-w-0 truncate">
                      {opt.icon && <span className="shrink-0">{opt.icon}</span>}
                      <span className="truncate">{opt.label}</span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {opt.badge && (
                        <span
                          className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                            isSelected
                              ? 'bg-sky-200/70 text-sky-900 border border-sky-300/60'
                              : 'bg-slate-100 text-slate-500 border border-slate-200/60'
                          }`}
                        >
                          {opt.badge}
                        </span>
                      )}
                      {isSelected && <Check className="w-3.5 h-3.5 text-sky-600" />}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
