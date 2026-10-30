"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmAction } from "@/components/ui/ConfirmAction";
import { errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";

import { endMyDevice, getMyDevices, sortDevices, type Device } from "./devices";

/*
 * "My devices" (Week 11): every place this person is signed in. A phone left at the
 * clinic or a shared computer can be signed out from here, at once, without touching
 * this device. To sign out of this one, use "Sign out" at the top.
 */
export function DeviceList() {
  const devices = useQuery({ queryKey: ["my-devices"], queryFn: getMyDevices });

  return (
    <section className="grid gap-6">
      <div>
        <p className="eyebrow">Account</p>
        <h1 className="mb-1">My devices</h1>
        <p className="text-sm">
          Where you are signed in now. If a device is lost, or you forgot to sign out of a
          shared computer, sign it out here: it stops working at once.
        </p>
      </div>
      <section className="card" aria-live="polite">
        {devices.isPending && <p>Loading...</p>}
        {devices.isError && (
          <p role="alert" className="error">
            {errorMessage(devices.error)}
          </p>
        )}
        <ul className="grid gap-3">
          {sortDevices(devices.data ?? []).map((device) => (
            <DeviceRow key={device.id} device={device} />
          ))}
        </ul>
      </section>
    </section>
  );
}

function DeviceRow({ device }: { device: Device }) {
  const queryClient = useQueryClient();
  const end = useMutation({
    mutationFn: () => endMyDevice(device.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["my-devices"] }),
  });

  return (
    <li className="grid gap-1 border-t border-line pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="font-semibold">{device.label}</span>
        {device.current && (
          <span className="badge bg-accent-soft text-accent">This device</span>
        )}
        {!device.current && (
          <span className="ml-auto">
            <ConfirmAction
              label="Sign out this device"
              question="Sign this device out now?"
              pending={end.isPending}
              onConfirm={() => end.mutate()}
            />
          </span>
        )}
      </div>
      <p className="m-0 text-sm">
        Signed in {formatDateTime(device.created_at)} · last used{" "}
        {formatDateTime(device.last_seen_at)}
      </p>
      {end.isError && (
        <p role="alert" className="error">
          {errorMessage(end.error)}
        </p>
      )}
    </li>
  );
}
