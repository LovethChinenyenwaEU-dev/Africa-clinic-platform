"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { errorMessage } from "@/lib/api-client";

import { addPrice, changePrice, getPrices } from "./api";
import { formatNaira, nairaInput, parseNaira } from "./money";
import type { Price } from "./schemas";

/*
 * The clinic's services and prices. Everyone who bills reads it; only admins add,
 * change, retire or bring back a service. Invoices already written keep the price
 * they copied, so a change here never alters a bill.
 */
export function PriceList({ canEdit }: { canEdit: boolean }) {
  const queryClient = useQueryClient();
  const key = ["prices", canEdit];
  const prices = useQuery({ queryKey: key, queryFn: () => getPrices(canEdit) });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["prices"] });

  return (
    <section className="grid gap-6">
      <div>
        <h1 className="mb-1">Prices</h1>
        <p className="text-sm">
          {canEdit
            ? "Add the services the clinic charges for. A retired service can no longer be billed, but old invoices keep it."
            : "The services the clinic charges for. Only an admin can change them."}
        </p>
      </div>

      <section aria-labelledby="price-list-heading" className="card">
        <h2 id="price-list-heading" className="mb-0">
          Services
        </h2>
        {prices.isPending && <p>Loading...</p>}
        {prices.isError && (
          <p role="alert" className="error">
            {errorMessage(prices.error)}
          </p>
        )}
        {prices.data?.length === 0 && <p>No services yet.</p>}
        {prices.data && prices.data.length > 0 && (
          <ul className="grid gap-2">
            {prices.data.map((price) => (
              <PriceRow key={price.id} price={price} canEdit={canEdit} onChanged={refresh} />
            ))}
          </ul>
        )}
      </section>

      {canEdit && <AddPriceForm onAdded={refresh} />}
    </section>
  );
}

function PriceRow({
  price,
  canEdit,
  onChanged,
}: {
  price: Price;
  canEdit: boolean;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState(nairaInput(price.price_kobo));
  const [problem, setProblem] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: (changes: Parameters<typeof changePrice>[1]) => changePrice(price, changes),
    onSuccess: () => {
      setEditing(false);
      onChanged();
    },
  });

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const kobo = parseNaira(amount);
    if (kobo === null) return setProblem("Type the price in naira, for example 5000 or 5,000.50.");
    setProblem(null);
    change.mutate({ price_kobo: kobo });
  }

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2">
      <span className={price.active ? "font-semibold" : "font-semibold text-muted line-through"}>
        {price.name}
      </span>
      {price.code && <span className="font-mono text-sm">{price.code}</span>}
      {!price.active && <span className="badge bg-gray-200 text-gray-800">Retired</span>}
      {!editing && <span className="ml-auto font-mono">{formatNaira(price.price_kobo)}</span>}
      {canEdit && !editing && (
        <span className="flex gap-2">
          {price.active && (
            <button type="button" className="button-secondary" onClick={() => setEditing(true)}>
              Change price
            </button>
          )}
          <button
            type="button"
            className="button-secondary"
            disabled={change.isPending}
            onClick={() => change.mutate({ active: !price.active })}
          >
            {price.active ? "Retire" : "Bring back"}
          </button>
        </span>
      )}
      {editing && (
        <form className="ml-auto flex flex-wrap items-end gap-2" onSubmit={save} noValidate>
          <div className="field">
            <label htmlFor={`price-${price.id}`}>New price (₦)</label>
            <input
              id={`price-${price.id}`}
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              aria-invalid={problem ? true : undefined}
            />
          </div>
          <button className="button" type="submit" disabled={change.isPending}>
            Save
          </button>
          <button type="button" className="button-secondary" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </form>
      )}
      {(problem || change.isError) && (
        <p role="alert" className="error w-full">
          {problem ?? errorMessage(change.error)}
        </p>
      )}
    </li>
  );
}

function AddPriceForm({ onAdded }: { onAdded: () => void }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [amount, setAmount] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: addPrice,
    onSuccess: () => {
      setName("");
      setCode("");
      setAmount("");
      onAdded();
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const kobo = parseNaira(amount);
    if (!name.trim()) return setProblem("Give the service a name.");
    if (kobo === null) return setProblem("Type the price in naira, for example 5000 or 5,000.50.");
    setProblem(null);
    add.mutate({ name: name.trim(), code: code.trim(), price_kobo: kobo });
  }

  return (
    <form
      className="card grid gap-3 sm:grid-cols-3"
      onSubmit={handleSubmit}
      noValidate
      aria-labelledby="add-price-heading"
    >
      <h2 id="add-price-heading" className="mb-0 sm:col-span-3">
        Add a service
      </h2>
      <div className="field">
        <label htmlFor="price-name">Name</label>
        <input id="price-name" value={name} onChange={(event) => setName(event.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="price-code">Code (optional)</label>
        <input id="price-code" value={code} onChange={(event) => setCode(event.target.value)} />
      </div>
      <div className="field">
        <label htmlFor="price-amount">Price (₦)</label>
        <input
          id="price-amount"
          inputMode="decimal"
          placeholder="5,000"
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </div>
      {(problem || add.isError) && (
        <p role="alert" className="error sm:col-span-3">
          {problem ?? errorMessage(add.error)}
        </p>
      )}
      <div className="sm:col-span-3">
        <button className="button" type="submit" disabled={add.isPending}>
          {add.isPending ? "Adding..." : "Add service"}
        </button>
      </div>
    </form>
  );
}
