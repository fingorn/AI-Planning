from aimacode.planning import Action
from aimacode.search import Problem
from aimacode.utils import expr
from lp_utils import decode_state


class PgNode():
    """Base class for planning graph nodes.

    includes instance sets common to both types of nodes used in a planning graph
    parents: the set of nodes in the previous level
    children: the set of nodes in the subsequent level
    mutex: the set of sibling nodes that are mutually exclusive with this node
    """

    def __init__(self):
        self.parents = set()
        self.children = set()
        self.mutex = set()

    def is_mutex(self, other) -> bool:
        """Boolean test for mutual exclusion

        :param other: PgNode
            the other node to compare with
        :return: bool
            True if this node and the other are marked mutually exclusive (mutex)
        """
        if other in self.mutex:
            return True
        return False

    def show(self):
        """helper print for debugging shows counts of parents, children, siblings

        :return:
            print only
        """
        print("{} parents".format(len(self.parents)))
        print("{} children".format(len(self.children)))
        print("{} mutex".format(len(self.mutex)))


class PgNode_s(PgNode):
    """A planning graph node representing a state (literal fluent) from a
    planning problem.

    Args:
    ----------
    symbol : str
        A string representing a literal expression from a planning problem
        domain.

    is_pos : bool
        Boolean flag indicating whether the literal expression is positive or
        negative.
    """

    def __init__(self, symbol: str, is_pos: bool):
        """S-level Planning Graph node constructor

        :param symbol: expr
        :param is_pos: bool
        Instance variables calculated:
            literal: expr
                    fluent in its literal form including negative operator if applicable
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous A level; initially empty
            children: set of nodes connected to this node in next A level; initially empty
            mutex: set of sibling S-nodes that this node has mutual exclusion with; initially empty
        """
        PgNode.__init__(self)
        self.symbol = symbol
        self.is_pos = is_pos
        self.__hash = None

    def show(self):
        """helper print for debugging shows literal plus counts of parents,
        children, siblings

        :return:
            print only
        """
        if self.is_pos:
            print("\n*** {}".format(self.symbol))
        else:
            print("\n*** ~{}".format(self.symbol))
        PgNode.show(self)

    def __eq__(self, other):
        """equality test for nodes - compares only the literal for equality

        :param other: PgNode_s
        :return: bool
        """
        return (isinstance(other, self.__class__) and
                self.is_pos == other.is_pos and
                self.symbol == other.symbol)

    def __hash__(self):
        self.__hash = self.__hash or hash(self.symbol) ^ hash(self.is_pos)
        return self.__hash


class PgNode_a(PgNode):
    """A-type (action) Planning Graph node - inherited from PgNode """


    def __init__(self, action: Action):
        """A-level Planning Graph node constructor

        :param action: Action
            a ground action, i.e. this action cannot contain any variables
        Instance variables calculated:
            An A-level will always have an S-level as its parent and an S-level as its child.
            The preconditions and effects will become the parents and children of the A-level node
            However, when this node is created, it is not yet connected to the graph
            prenodes: set of *possible* parent S-nodes
            effnodes: set of *possible* child S-nodes
            is_persistent: bool   True if this is a persistence action, i.e. a no-op action
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous S level; initially empty
            children: set of nodes connected to this node in next S level; initially empty
            mutex: set of sibling A-nodes that this node has mutual exclusion with; initially empty
        """
        PgNode.__init__(self)
        self.action = action
        self.prenodes = self.precond_s_nodes()
        self.effnodes = self.effect_s_nodes()
        self.is_persistent = self.prenodes == self.effnodes
        self.__hash = None

    def show(self):
        """helper print for debugging shows action plus counts of parents, children, siblings

        :return:
            print only
        """
        print("\n*** {!s}".format(self.action))
        PgNode.show(self)

    def precond_s_nodes(self):
        """precondition literals as S-nodes (represents possible parents for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `prenodes` attribute.

        :return: set of PgNode_s
        """
        nodes = set()
        for p in self.action.precond_pos:
            nodes.add(PgNode_s(p, True))
        for p in self.action.precond_neg:
            nodes.add(PgNode_s(p, False))
        return nodes

    def effect_s_nodes(self):
        """effect literals as S-nodes (represents possible children for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `effnodes` attribute.

        :return: set of PgNode_s
        """
        nodes = set()
        for e in self.action.effect_add:
            nodes.add(PgNode_s(e, True))
        for e in self.action.effect_rem:
            nodes.add(PgNode_s(e, False))
        return nodes

    def __eq__(self, other):
        """equality test for nodes - compares only the action name for equality

        :param other: PgNode_a
        :return: bool
        """
        return (isinstance(other, self.__class__) and
                self.is_persistent == other.is_persistent and
                self.action.name == other.action.name and
                self.action.args == other.action.args)

    def __hash__(self):
        self.__hash = self.__hash or hash(self.action.name) ^ hash(self.action.args)
        return self.__hash


def mutexify(node1: PgNode, node2: PgNode):
    """ adds sibling nodes to each other's mutual exclusion (mutex) set. These should be sibling nodes!

    :param node1: PgNode (or inherited PgNode_a, PgNode_s types)
    :param node2: PgNode (or inherited PgNode_a, PgNode_s types)
    :return:
        node mutex sets modified
    """
    if type(node1) != type(node2):
        raise TypeError('Attempted to mutex two nodes of different types')
    node1.mutex.add(node2)
    node2.mutex.add(node1)


class PlanningGraph():
    """
    A planning graph as described in chapter 10 of the AIMA text. The planning
    graph can be used to reason about 
    """

    def __init__(self, problem: Problem, state: str, serial_planning=True):
        """
        :param problem: PlanningProblem (or subclass such as AirCargoProblem or HaveCakeProblem)
        :param state: str (will be in form TFTTFF... representing fluent states)
        :param serial_planning: bool (whether or not to assume that only one action can occur at a time)
        Instance variable calculated:
            fs: FluentState
                the state represented as positive and negative fluent literal lists
            all_actions: list of the PlanningProblem valid ground actions combined with calculated no-op actions
            s_levels: list of sets of PgNode_s, where each set in the list represents an S-level in the planning graph
            a_levels: list of sets of PgNode_a, where each set in the list represents an A-level in the planning graph
        """
        self.problem = problem
        self.fs = decode_state(state, problem.state_map)
        self.serial = serial_planning
        self.all_actions = self.problem.actions_list + self.noop_actions(self.problem.state_map)
        self.s_levels = []
        self.a_levels = []
        self.create_graph()
        
        self.goal_states = set()
        self.goal_states.update( set(PgNode_s(s,True) for s in self.problem.goal ))
        
    def noop_actions(self, literal_list):
        """create persistent action for each possible fluent

        "No-Op" actions are virtual actions (i.e., actions that only exist in
        the planning graph, not in the planning problem domain) that operate
        on each fluent (literal expression) from the problem domain. No op
        actions "pass through" the literal expressions from one level of the
        planning graph to the next.

        The no-op action list requires both a positive and a negative action
        for each literal expression. Positive no-op actions require the literal
        as a positive precondition and add the literal expression as an effect
        in the output, and negative no-op actions require the literal as a
        negative precondition and remove the literal expression as an effect in
        the output.

        This function should only be called by the class constructor.

        :param literal_list:
        :return: list of Action
        """
        action_list = []
        for fluent in literal_list:
            act1 = Action(expr("Noop_pos({})".format(fluent)), ([fluent], []), ([fluent], []))
            action_list.append(act1)
            act2 = Action(expr("Noop_neg({})".format(fluent)), ([], [fluent]), ([], [fluent]))
            action_list.append(act2)
        return action_list

    def create_graph(self):
        """ build a Planning Graph as described in Russell-Norvig 3rd Ed 10.3 or 2nd Ed 11.4

        The S0 initial level has been implemented for you.  It has no parents and includes all of
        the literal fluents that are part of the initial state passed to the constructor.  At the start
        of a problem planning search, this will be the same as the initial state of the problem.  However,
        the planning graph can be built from any state in the Planning Problem

        This function should only be called by the class constructor.

        :return:
            builds the graph by filling s_levels[] and a_levels[] lists with node sets for each level
        """
        # the graph should only be built during class construction
        if (len(self.s_levels) != 0) or (len(self.a_levels) != 0):
            raise Exception(
                'Planning Graph already created; construct a new planning graph for each new state in the planning sequence')

        # initialize S0 to literals in initial state provided.
        leveled = False
        level = 0
        self.s_levels.append(set())  # S0 set of s_nodes - empty to start
        # for each fluent in the initial state, add the correct literal PgNode_s
        for literal in self.fs.pos:
            self.s_levels[level].add(PgNode_s(literal, True))
        for literal in self.fs.neg:
            self.s_levels[level].add(PgNode_s(literal, False))
            
            
        # no mutexes at the first level

        # continue to build the graph alternating A, S levels until last two S levels contain the same literals,
        # i.e. until it is "leveled"
#        print("Current level :",level)


#        testCounter = 0
        while not leveled:
            self.add_action_level(level)
            self.update_a_mutex(self.a_levels[level])

            level += 1
            self.add_literal_level(level)
            self.update_s_mutex(self.s_levels[level])

#            testCounter+=1
#            if testCounter >2:
#                leveled= True
                
            if self.s_levels[level] == self.s_levels[level - 1]:
#                print("State leveled at ", level -1 , " = " , level)
                leveled = True

    def add_action_level(self, level):
        """ add an A (action) level to the Planning Graph

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds A nodes to the current level in self.a_levels[level]
        """
        # TODO add action A level to the planning graph as described in the Russell-Norvig text
        # 1. determine what actions to add and create those PgNode_a objects
        # 2. connect the nodes to the previous S literal level
        # for example, the A0 level will iterate through all possible actions for the problem and add a PgNode_a to a_levels[0]
        #   see if all prerequisite literals for the action hold in S0.  This can be accomplished by testing
        #   to see if a proposed PgNode_a has prenodes that are a subset of the previous S level.  Once an
        #   action node is added, it MUST be connected to the S node instances in the appropriate s_level set.
        
#        print("************* ADD ACTION LEVEL",level," *****************")
        self.a_levels.append(set())
#        print("a_levels",self.a_levels, " in level :", level)
        
        previous_s = self.s_levels[level] #returns a set of the previous S level that contains all literals as PgNode_s true / false
#        print("previous s len :", len(previous_s))
        
#        print("=====================================")
#        print("Node S states:")

#        for state in previous_s:
#            print("{} {}".format("+" if state.is_pos else "-", state.symbol))
            
#        print("=====================================")
        
        for action in self.all_actions:
#            print("Action : ", action.name)
            add_action = True
            parent_s_nodes = set()
            short_circuit = False
            for precond_pos in action.precond_pos:
                
                #Convert precond_pos to PgNode_s format
                node_s_pos = PgNode_s(precond_pos,True)
#                print("pgNode_s format :", node_s_pos.show())
                
                if node_s_pos not in previous_s:
                    add_action = False
#                    print(action.name, " precondition : ", precond_pos , " not a prenode in state ", level)
                    short_circuit = True
                    break
                else:
                    
                    parent_s_nodes.add(node_s_pos)
            
            if not short_circuit:
                for precond_neg in action.precond_neg:
                    node_s_neg = PgNode_s(precond_neg,False)
                    if node_s_neg not in previous_s:
                        add_action = False
#                        print(action.name, " precondition : -", precond_neg , " not a prenode in state ", level)
                        break
                    else:
                        parent_s_nodes.add(node_s_neg)
            if add_action:
                a_node = PgNode_a(action)
                
                #Update childen set of parent s nodes
                for s_node in self.s_levels[level]:
                    if s_node in parent_s_nodes:
                        s_node.children.add(a_node)
#                
                #Update current action's parent node
                a_node.parents.update(parent_s_nodes)
                
                #Add node to levels
                self.a_levels[level].add(a_node)
                
#                print(action.name, " added to actions at level ", level, ". Preconditions :+", str(action.precond_pos), "-",str(action.precond_neg),
#                      ". Effects : +", str(action.effect_add), " -",str(action.effect_rem))
        
#==============================================================================
# 
#         print("Debug previous s_level[{}] values".format(level))
#         for s in self.s_levels[level]:
#             print("{}".format(s.show()))
#             if s.children:
#                 print("Children Actions: {} ".format(",".join( a.action.name for a in s.children)))
#         print("################## ADD ACTION LEVEL END ##################")
#         
#         
#==============================================================================
                

    def add_literal_level(self, level):
        """ add an S (literal) level to the Planning Graph

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds S nodes to the current level in self.s_levels[level]
        """
        # TODO add literal S level to the planning graph as described in the Russell-Norvig text
        # 1. determine what literals to add
        # 2. connect the nodes
        # for example, every A node in the previous level has a list of S nodes in effnodes that represent the effect
        #   produced by the action.  These literals will all be part of the new S level.  Since we are working with sets, they
        #   may be "added" to the set without fear of duplication.  However, it is important to then correctly create and connect
        #   all of the new S nodes as children of all the A nodes that could produce them, and likewise add the A nodes to the
        #   parent sets of the S nodes
        
        #Add a new s level to s_levels list
#        print("************* ADD S_LEVEL",level," *****************")
        
        self.s_levels.append(set())
        
        #Before adding parents/children connection
#==============================================================================
#         Old / Wrong code
# #        print("add literal level :", level)
#         pre_a_level = self.a_levels[level-1] #previous action level set of nodes
#         for action_node in pre_a_level:
# #            print("For Action :", node.action)
#             effnodes = action_node.effnodes
#             for effnode in effnodes:
# #                effnode.parents.add(action_node)
#                 #just add effnode (it is already in PgNode_s format)
#                 self.s_levels[level].add(effnode)
#         
#==============================================================================
        
        
        for pre_a_node in self.a_levels[level-1]:
            for effnode in pre_a_node.effnodes:
                effnode.parents.add(pre_a_node)
                pre_a_node.children.add(effnode)
                self.s_levels[level].add(effnode)
                
        

#==============================================================================
#           #DEbug
#         print("Current S levels length:",len(self.s_levels))
#         print("s_level[",level,"]")
#         for s_node in self.s_levels[level]:
#             #print("{} s_node : {}".format("+" if s_node.is_pos else "-", s_node.symbol))
#             print("{}".format(s_node.show()))
#             if s_node.parents:
#                 print("s node parent action : {}".format(",".join(a.action.name for a in s_node.parents)))
#             if s_node.children:
#                 print("s node children states : {}".format(",".join(s.symbol for s in s_node.children)))
#                 
#                 
#==============================================================================
#        print("################## END S_LEVEL",level," ##################")
        

    def update_a_mutex(self, nodeset):
        """ Determine and update sibling mutual exclusion for A-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between two actions a given level
        if the planning graph is a serial planning graph and the pair are nonpersistence actions
        or if any of the three conditions hold between the pair:
           Inconsistent Effects
           Interference
           Competing needs

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        """
        
#        print("in update a mutex, nodeset length :" , len(nodeset))
        
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if (self.serialize_actions(n1, n2) or
                        self.inconsistent_effects_mutex(n1, n2) or
                        self.interference_mutex(n1, n2) or
                        self.competing_needs_mutex(n1, n2)):
                    mutexify(n1, n2)

    def serialize_actions(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for mutual exclusion, returning True if the
        planning graph is serial, and if either action is persistent; otherwise
        return False.  Two serial actions are mutually exclusive if they are
        both non-persistent.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        #
        if not self.serial:
            return False
        if node_a1.is_persistent or node_a2.is_persistent:
            return False
        return True

    def inconsistent_effects_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for inconsistent effects, returning True if
        one action negates an effect of the other, and False otherwise.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        # TODO test for Inconsistent Effects between nodes
        
        for a1_effect_add in node_a1.action.effect_add:
#            for a2_effect_rem in node_a2.action.effect_rem:
#                if a1_effect_add == a2_effect_rem:
#                    print("Inconsistent_effect_mutex for ", node_a1.action.name, " : ", a1_effect_add)
#                    return True
            if a1_effect_add in node_a2.action.effect_rem:
#                print("Inconsistent_effect_mutex for ", node_a1.action.name, " : ", a1_effect_add)
                return True
                    
        for a1_effect_rem in node_a1.action.effect_rem:
#            for a2_effect_add in node_a2.action.effect_add:
#                if a1_effect_rem == a2_effect_add:
#                    print("Inconsistent_effect_mutex for ", node_a1.action.name, " : ", a1_effect_add)
#                    return True
            if a1_effect_rem in node_a2.action.effect_add:
#                print("Inconsistent_effect_mutex for ", node_a1.action.name, " : ", a1_effect_add)
                return True
        
#        print("no negative inconsistence mutext between ", node_a1.action.name, " and ", node_a2.action.name)
        return False

    def interference_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for mutual exclusion, returning True if the 
        effect of one action is the negation of a precondition of the other.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        # TODO test for Interference between nodes
        
#==============================================================================
#         #DEBUG
#         print("********* Inteference mutex ***********")
#         print("between action :", node_a1.action.name, "  - ", node_a2.action.name)
#         print("Action 1 {} pos preconditions : {}".format(node_a1.action.name ,",".join( str(condition) for condition in node_a1.action.precond_pos)))
#         print("Action 2 {} neg effects : {}".format(node_a2.action.name ,",".join( str(condition) for condition in node_a2.action.effect_rem)))
#         
#         print("Action 1 {} pos effects : {}".format(node_a1.action.name ,",".join( str(condition) for condition in node_a1.action.effect_add)))
#         print("Action 2 {} neg preconditions : {}".format(node_a2.action.name ,",".join( str(condition) for condition in node_a2.action.precond_neg)))
#         
#         print("Action 1 {} neg preconditions : {}".format(node_a1.action.name ,",".join( str(condition) for condition in node_a1.action.precond_neg)))
#         print("Action 2 {} pos effects : {}".format(node_a2.action.name ,",".join( str(condition) for condition in node_a2.action.effect_add)))
#         
#         print("Action 1 {} neg effects : {}".format(node_a1.action.name ,",".join( str(condition) for condition in node_a1.action.effect_rem)))
#         print("Action 2 {} pos preconditions : {}".format(node_a2.action.name ,",".join( str(condition) for condition in node_a2.action.precond_pos)))
#         
#==============================================================================
        
        for a1_effect_add in node_a1.action.effect_add:
#            print("a1 add effect :", a1_effect_add)
            if a1_effect_add in node_a2.action.precond_neg:
                return True
        for a1_effect_rem in node_a1.action.effect_rem:
#            print("a1 remove effect :" , a1_effect_rem)
            if a1_effect_rem in node_a2.action.precond_pos:
                return True
        for a1_precond_pos in node_a1.action.precond_pos:
            if a1_precond_pos in node_a2.action.effect_rem:
                return True
        for a1_precond_neg in node_a1.action.precond_neg:
            if a1_precond_neg in node_a2.action.effect_add:
                return True
        
#        print("################### Inteference mutex END ###################### ")
        return False

    def competing_needs_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        """
        Test a pair of actions for mutual exclusion, returning True if one of
        the precondition of one action is mutex with a precondition of the
        other action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        """
        
#==============================================================================
#         
#         print("************************ Competing needs mutex **************************")
#         print("Action 1 {} pos preconditions : {}".format(node_a1.action.name ,",".join( str(condition) for condition in node_a1.action.precond_pos)))
#         print("Action 2 {} neg preconditions : {}".format(node_a2.action.name ,",".join( str(condition) for condition in node_a2.action.precond_neg)))
#         
#         print("Action 1 {} neg preconditions : {}".format(node_a1.action.name ,",".join( str(condition) for condition in node_a1.action.precond_neg)))
#         print("Action 2 {} pos preconditions : {}".format(node_a2.action.name ,",".join( str(condition) for condition in node_a2.action.precond_pos)))
#         
#         for a1_precond_pos in node_a1.action.precond_pos:
#             if a1_precond_pos in node_a2.action.precond_neg:
#                 return True
#         for a1_precond_neg in node_a1.action.precond_neg:
#             if a1_precond_neg in node_a2.action.precond_pos:
#                 return True
# 
# 
#==============================================================================

        # TODO test for Competing Needs between nodes
        
        #Get parent of the two nodes, compare if they are mutex
        #if they are mutex, return True
        for a1_parent_s in node_a1.parents:
            for a2_parent_s in node_a2.parents:
                if a2_parent_s.is_mutex(a1_parent_s):
                    return True
        
#        print("************************ Competing needs mutex END **************************")
        return False

    def update_s_mutex(self, nodeset: set):
        """ Determine and update sibling mutual exclusion for S-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between literals at a given level
        if either of the two conditions hold between the pair:
           Negation
           Inconsistent support

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        """
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if self.negation_mutex(n1, n2) or self.inconsistent_support_mutex(n1, n2):
                    mutexify(n1, n2)

    def negation_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s) -> bool:
        """
        Test a pair of state literals for mutual exclusion, returning True if
        one node is the negation of the other, and False otherwise.

        HINT: Look at the PgNode_s.__eq__ defines the notion of equivalence for
        literal expression nodes, and the class tracks whether the literal is
        positive or negative.

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        """
        # TODO test for negation between nodes
        if node_s1.symbol == node_s2.symbol:
            if node_s1 != node_s2:
                return True
        
        return False

    def inconsistent_support_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s):
        """
        Test a pair of state literals for mutual exclusion, returning True if
        there are no actions that could achieve the two literals at the same
        time, and False otherwise.  In other words, the two literal nodes are
        mutex if all of the actions that could achieve the first literal node
        are pairwise mutually exclusive with all of the actions that could
        achieve the second literal node.

        HINT: The PgNode.is_mutex method can be used to test whether two nodes
        are mutually exclusive.

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        """
        # TODO test for Inconsistent Support between nodes
        
#        print("Inconsistent support test for {}{} and {}{}".format("+" if node_s1.is_pos else "-",node_s1.symbol, "+" if node_s1.is_pos else "-", node_s2.symbol))
        
        result = False
        for parent_a in node_s1.parents:
            for parent_b in node_s2.parents:
                if parent_a.is_mutex(parent_b):
#                    print("Inconsistent support action are mutex: S1: {}{} S2: {}{}".format("+" if node_s1.is_pos else "-",node_s1.symbol, "+" if node_s1.is_pos else "-", node_s2.symbol))
#                    print("PA:{} - children: {}".format( parent_a.action.name , ",".join( ("{}{}".format("+" if s.is_pos else "-",str(s.symbol))) for s in parent_a.children )))
#                    print("PB:{} - children: {}".format(parent_b.action.name ,",".join( ("{}{}".format("+" if s.is_pos else "-",str(s.symbol)) for s in parent_b.children ))))
                    result = True
                    
                    if node_s1 in parent_a.children and node_s2 in parent_a.children or node_s1 in parent_b.children and node_s2 in parent_b.children:
#                        print("{}{} {}{} are both children of parent_a".format("+" if node_s1.is_pos else "-" ,node_s1.symbol,"+" if node_s1.is_pos else "-",node_s2.symbol))
                        return False
            
            
            
        return result

    def h_levelsum(self) -> int:
        """The sum of the level costs of the individual goals (admissible if goals independent)

        :return: int
        """
        level_sum = 0
        # TODO implement
        # for each goal in the problem, determine the level cost, then add them together
        
        #get each goal

        
        #Loop through s_levels[]. if all the goal conditions are in a s_level, add that current level to level_sum
#        print("h_levelsum Goals:")
#        print("{}".format(  ",".join( str("{}{}".format("+" if s.is_pos else "-",s.symbol)) for s in self.goal_states )))
        
        for goal_fluent in self.goal_states:
            for i, s_level in enumerate(self.s_levels):
#                print("s-level{}, Contents: {}".format(i, "{}".format( ",".join( "{}{}".format("+" if s.is_pos else "-",str(s.symbol)) for s in s_level))))
                if goal_fluent in s_level:
#                    print("Goal {}{} is in s_level[{}]".format("+" if goal_fluent.is_pos else "-" ,goal_fluent.symbol, i))
                    level_sum += i
#                    print("level sum incremented to:",level_sum)
                    break
        
        return level_sum
