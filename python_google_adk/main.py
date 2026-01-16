from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google_adk_arcade.tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage

import os

load_dotenv(override=True)


async def main():
    app_name = "my_agent"
    user_id = os.getenv("ARCADE_USER_ID")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    agent_tools = await get_arcade_tools(
        client, tools=["PagerdutyApi_ListExistingIncidents", "PagerdutyApi_GetIncidentDetails", "PagerdutyApi_ListIncidentLogEntries", "PagerdutyApi_ListIncidentAlerts", "PagerdutyApi_ListIncidentNotes", "PagerdutyApi_AddIncidentNote", "PagerdutyApi_UpdateIncidentStatus", "PagerdutyApi_GetServiceDetails", "PagerdutyApi_ListServices", "DatadogApi_ListLogs", "DatadogApi_ListLogsMatchingQuery", "DatadogApi_SearchDatadogEvents", "DatadogApi_GetEventDetails", "DatadogApi_SearchDatadogIncidents", "DatadogApi_GetIncidentDetails", "DatadogApi_SearchDatadogIssues", "DatadogApi_GetErrorTrackingIssueDetails", "DatadogApi_SearchRumEvents", "DatadogApi_ListRumEvents", "DatadogApi_QueryTimeseriesData", "DatadogApi_QueryScalarData"], toolkits=["Slack", "Gmail", "GoogleCalendar"]
    )

    for tool in agent_tools:
        await auth_tool(client, tool_name=tool.name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=f"openai/{os.environ["OPENAI_MODEL"]}"),
        name="google_agent",
        instruction="You are a Debug Investigation Agent that helps investigate and resolve incidents. When triggered with an incident, follow this workflow:

1. **Retrieve Incident Details**: Use PagerDuty tools to get full incident context, affected services, and existing notes.

2. **Gather Log Data**: Query Datadog logs around the incident timeframe. Search for errors, exceptions, and anomalies. Use RUM events for user impact analysis.

3. **Correlate Issues**: Search for related Datadog incidents, error tracking issues, and events that might explain the root cause.

4. **Analyze Metrics**: Query relevant time series and scalar metrics to understand system behavior during the incident.

5. **Communicate Findings**: Post incident analysis updates to Slack to keep stakeholders informed.

6. **Document Root Cause**: Once investigation is complete, send a root cause analysis summary via Gmail to relevant parties.

7. **Schedule Review**: Create a Google Calendar event for a post-incident review meeting with the team.

Always add investigation notes to the PagerDuty incident and update its status as the investigation progresses.",
        description="A debug investigation agent that integrates PagerDuty, Datadog, Slack, Gmail, and Google Calendar to streamline incident investigation and resolution workflows",
        tools=agent_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())