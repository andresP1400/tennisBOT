"use client"

import * as React from "react"
import {
  IconChartBar,
  IconDashboard,
  IconDatabase,
  IconReport,
  IconSettings,
  IconTrophy,
  IconBallTennis,
  IconAdjustments,
  IconTable,
  IconClipboardList,
  IconLivePhoto,
  IconUsers,
} from "@tabler/icons-react"

import { NavMain } from "@/components/nav-main"
import { NavSecondary } from "@/components/nav-secondary"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

const data = {
  navMain: [
    {
      label: "Core",
      items: [
        {
          title: "Dashboard",
          url: "/dashboard",
          icon: IconDashboard,
        },
        {
          title: "Predict Match",
          url: "/dashboard/predict",
          icon: IconBallTennis,
        },
        {
          title: "Track Record",
          url: "/dashboard/track",
          icon: IconClipboardList,
        },
        {
          title: "Live Market",
          url: "/dashboard/live",
          icon: IconLivePhoto,
        },
        {
          title: "Model Analytics",
          url: "/dashboard/analytics",
          icon: IconChartBar,
        },
        {
          title: "Training Studio",
          url: "/dashboard/training",
          icon: IconAdjustments,
        },
      ]
    },
    {
      label: "Explore Data",
      items: [
        {
          title: "Match History",
          url: "/dashboard/history",
          icon: IconTrophy,
        },
        {
          title: "Raw Data",
          url: "/dashboard/data",
          icon: IconTable,
        },
        {
          title: "Feature Dataset",
          url: "/dashboard/features",
          icon: IconDatabase,
        },
      ]
    },
    {
      label: "Pipeline",
      items: [
        {
          title: "Evaluation Reports",
          url: "/dashboard/reports",
          icon: IconReport,
        }
      ]
    }
  ],
  navSecondary: [
    {
      title: "Players",
      url: "/dashboard/players",
      icon: IconUsers,
    },
    {
      title: "Settings",
      url: "/dashboard/settings",
      icon: IconSettings,
    },
  ]
}

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              className="data-[slot=sidebar-menu-button]:!p-1.5"
            >
              <a href="/dashboard">
                <IconBallTennis className="!size-5 text-emerald-400" />
                <span className="text-base font-semibold">TennisBot</span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain groups={data.navMain} />
        <NavSecondary items={data.navSecondary} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <div className="px-3 py-2 text-xs text-muted-foreground">
          v1.0.0 -- Stacking Ensemble
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
