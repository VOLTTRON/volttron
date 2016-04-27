Deprecated
==========

Declaratively attach topic prefix and additional tests for topic
matching to agent methods allowing for automated callback registration
and topic subscription.

Example:

::

        class MyAgent(BaseAgent):
            @match_regex('topic1/(sub|next|part)/title[1-9]')
            def on_subtopic(topic, headers, message, match):
                # This is only executed if topic matches regex
                ...

            @match_glob('root/sub/*/leaf')
            def on_leafnode(topic, headers, message, match):
                # This is only executed if topic matches glob
                ...

            @match_exact('building/xyz/unit/condenser')
            @match_start('campus/PNNL')
            @match_end('unit/blower')
            def on_multimatch(topic, headers, message, match):
                # Multiple matchers can be attached to a method
                ...

    '''

