using AtomSdk;
using AtomSdk.Models;
using AtomSdkExamples;

// 节点级调试流程：初始化、激活、更新。
// 参数顺序：graphName、nodeId、graphNodeId、innerNodeId、baseUrl；也可使用对应环境变量。
var graphName = ExampleSettings.ArgumentOrSetting(args, 0, "ATOM_GRAPH_NAME", ExampleSettings.GraphName);
var nodeId = ExampleSettings.ArgumentOrSetting(args, 1, "ATOM_NODE_ID", ExampleSettings.NodeId);
var graphNodeId = ExampleSettings.ArgumentOrSetting(args, 2, "ATOM_GRAPH_NODE_ID", ExampleSettings.GraphNodeId);
var innerNodeId = ExampleSettings.ArgumentOrSetting(args, 3, "ATOM_INNER_NODE_ID", ExampleSettings.InnerNodeId);
var baseUrl = ExampleSettings.ArgumentOrSetting(args, 4, "ATOM_BASE_URL", ExampleSettings.BaseUrl);
var client = new AtomClient(baseUrl);
var graphOpened = false;
var subgraphOpened = false;

try
{
    var graph = await client.Graph.OpenGraphInfoAsync(graphName);
    graphOpened = true;
    ExampleSettings.PrintStatus("打开主图", graph.Status, graph.Timestamp);

    var node = new NodeRef(graphName, nodeId);
    var initial = await client.Node.InitialNodeInfoAsync(node);
    ExampleSettings.PrintStatus("初始化主图节点", initial.Status, initial.Timestamp);

    var activated = await client.Node.ActivateNodeResultAsync(node);
    ExampleSettings.PrintStatus("激活主图节点", activated.Status, activated.Timestamp);

    var updated = await client.Node.UpdateNodeResultAsync(node);
    ExampleSettings.PrintStatus("更新主图节点", updated.Status, updated.Timestamp);

    var subgraph = new SubGraphRef(graphName, graphNodeId);
    var subgraphOpen = await client.GraphNode.OpenGraphInfoAsync(subgraph);
    subgraphOpened = true;
    ExampleSettings.PrintStatus("打开子图", subgraphOpen.Status, subgraphOpen.Timestamp);

    var innerNode = new SubGraphNodeRef(graphName, graphNodeId, innerNodeId);
    var innerInitial = await client.GraphNode.InitialNodeInfoAsync(innerNode);
    ExampleSettings.PrintStatus("初始化子图内部节点", innerInitial.Status, innerInitial.Timestamp);

    var innerActivated = await client.GraphNode.ActivateNodeResultAsync(innerNode);
    ExampleSettings.PrintStatus("激活子图内部节点", innerActivated.Status, innerActivated.Timestamp);

    var innerUpdated = await client.GraphNode.UpdateNodeResultAsync(innerNode);
    ExampleSettings.PrintStatus("更新子图内部节点", innerUpdated.Status, innerUpdated.Timestamp);
}
finally
{
    // 这里只释放编辑态资源，不删除图、节点或子图节点。
    if (subgraphOpened)
    {
        await client.GraphNode.ReleaseGraphAsync(new SubGraphRef(graphName, graphNodeId));
    }

    if (graphOpened)
    {
        await client.Graph.ReleaseGraphAsync(graphName);
    }
}
