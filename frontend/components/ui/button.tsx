import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { clsx } from "clsx";
import type { ComponentProps } from "react";

const variants = cva("button", {
  variants: { variant: { primary: "button-primary", outline: "button-outline", ghost: "button-ghost" } },
  defaultVariants: { variant: "primary" },
});

export function Button({asChild = false, variant, className, ...props}: ComponentProps<"button"> &
  VariantProps<typeof variants> & {asChild?: boolean}) {
  const Comp = asChild ? Slot.Root : "button";
  return <Comp className={clsx(variants({variant}), className)} {...props}/>;
}
