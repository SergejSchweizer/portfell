import type { ReactNode } from "react";

export type ProgressStep = Readonly<{
  id: string;
  label: string;
  current?: boolean;
  disabled?: boolean;
}>;

export type ProgressStepperProps = Readonly<{
  steps: readonly ProgressStep[];
  children?: ReactNode;
}>;

export function ProgressStepper({ steps, children }: ProgressStepperProps) {
  return (
    <nav aria-label="Progress stepper" className="portfell-progress-stepper">
      {steps.map((step) => (
        <button
          key={step.id}
          type="button"
          aria-current={step.current ? "step" : undefined}
          disabled={step.disabled}
        >
          {step.label}
        </button>
      ))}
      {children}
    </nav>
  );
}
